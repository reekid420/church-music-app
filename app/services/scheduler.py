"""APScheduler-based scheduling service."""

import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from app.database import get_db_connection

logger = logging.getLogger(__name__)


class SchedulerService:
    """Manage scheduled audio playback with APScheduler."""

    def __init__(self, app, audio_player):
        self.app = app
        self.audio_player = audio_player
        # Use default MemoryJobStore – our schedules table is the source of truth
        # and we reload jobs on startup. SQLAlchemyJobStore fails because it tries
        # to pickle the Flask app (which contains un-picklable lambdas).
        self.scheduler = BackgroundScheduler(
            job_defaults={
                'coalesce': True,
                'max_instances': 1,
                'misfire_grace_time': 300
            }
        )
        self.scheduler.start()
        self._load_schedules_from_db()
        logger.info("Scheduler service started")

    def _load_schedules_from_db(self):
        """Load all enabled schedules from the DB and register jobs."""
        try:
            conn = get_db_connection(self.app)
            cursor = conn.execute(
                "SELECT * FROM schedules WHERE enabled = 1"
            )
            schedules = cursor.fetchall()
            conn.close()

            for schedule in schedules:
                self._register_job(dict(schedule))
            logger.info(f"Loaded {len(schedules)} schedules")
        except Exception as e:
            logger.error(f"Failed to load schedules: {e}")

    def _register_job(self, schedule):
        """Register a single schedule as an APScheduler job."""
        job_id = f"schedule_{schedule['id']}"

        # Remove existing job if present
        try:
            self.scheduler.remove_job(job_id)
        except Exception:
            pass

        try:
            if schedule['schedule_type'] == 'recurring':
                trigger = CronTrigger(
                    day_of_week=schedule.get('day_of_week', '*'),
                    hour=schedule.get('hour', 0),
                    minute=schedule.get('minute', 0)
                )
            elif schedule['schedule_type'] == 'one_time':
                run_date = schedule.get('run_date', '').strip()
                if not run_date:
                    logger.warning(f"Schedule {schedule['id']} missing run_date")
                    return
                # HTML datetime-local gives ISO 8601 e.g. "2026-03-04T16:30"
                try:
                    parsed_date = datetime.fromisoformat(run_date)
                except ValueError:
                    logger.error(f"Schedule {schedule['id']}: cannot parse run_date '{run_date}'")
                    return
                trigger = DateTrigger(run_date=parsed_date)
            elif schedule['schedule_type'] == 'automation':
                trigger = CronTrigger(
                    day_of_week=schedule.get('day_of_week', '*'),
                    hour=schedule.get('hour', 0),
                    minute=schedule.get('minute', 0),
                    start_date=schedule.get('start_date') or None,
                    end_date=schedule.get('end_date') or None
                )
            else:
                logger.warning(f"Unknown schedule type: {schedule['schedule_type']}")
                return

            job = self.scheduler.add_job(
                self._execute_schedule,
                trigger=trigger,
                id=job_id,
                name=schedule.get('name', 'Unnamed Schedule'),
                args=[schedule['id']],
                replace_existing=True
            )
            logger.info(
                f"Registered job: {job_id} ({schedule.get('name', 'unnamed')}), "
                f"next run: {job.next_run_time}"
            )
        except Exception as e:
            logger.error(f"Failed to register job {job_id}: {e}", exc_info=True)

    def _execute_schedule(self, schedule_id):
        """Execute a scheduled playback."""
        logger.info(f"Schedule {schedule_id} triggered, starting execution...")
        try:
            with self.app.app_context():
                conn = get_db_connection(self.app)
                cursor = conn.execute(
                    "SELECT * FROM schedules WHERE id = ?", (schedule_id,)
                )
                schedule = cursor.fetchone()
                if not schedule:
                    logger.warning(f"Schedule {schedule_id} not found in DB")
                    conn.close()
                    return

                schedule = dict(schedule)
                logger.info(
                    f"Executing schedule: {schedule['name']} "
                    f"(duration: {schedule['duration_minutes']} min, "
                    f"volume: {schedule.get('volume')}%)"
                )

                # Determine volume: use schedule-specific or fall back to default
                sched_volume = schedule.get('volume')
                if sched_volume is not None and sched_volume > 0:
                    target_volume = sched_volume
                else:
                    # Read current default volume from settings
                    row = conn.execute(
                        "SELECT value FROM settings WHERE key = 'default_volume'"
                    ).fetchone()
                    target_volume = int(row['value']) if row else 80
                    logger.info(f"Schedule has no custom volume, using default: {target_volume}%")

                # Set track volume (VLC internal), not global system volume
                self.audio_player.set_track_volume(target_volume)
                logger.info(f"Track volume set to {target_volume}%")

                # Play the playlist or song
                play_success = False
                if schedule.get('playlist_id'):
                    play_success = self.audio_player.play_playlist_by_id(
                        schedule['playlist_id'], conn
                    )
                elif schedule.get('song_id'):
                    play_success = self.audio_player.play_song_by_id(
                        schedule['song_id'], conn
                    )
                else:
                    logger.warning(f"Schedule {schedule_id} has no playlist or song")
                    conn.close()
                    return

                if play_success:
                    logger.info(f"Schedule '{schedule['name']}' playback started successfully")
                else:
                    logger.error(f"Schedule '{schedule['name']}' playback FAILED to start")

                # Set auto-stop timer
                if play_success and schedule.get('duration_minutes', 0) > 0:
                    self.audio_player.set_stop_timer(schedule['duration_minutes'])

                # Auto-remove one-time schedules after execution
                if schedule['schedule_type'] == 'one_time':
                    conn.execute(
                        "DELETE FROM schedules WHERE id = ?", (schedule_id,)
                    )
                    conn.commit()
                    logger.info(f"One-time schedule '{schedule['name']}' auto-removed after execution")

                conn.close()
        except Exception as e:
            logger.error(f"Schedule {schedule_id} execution failed: {e}", exc_info=True)

    def add_schedule(self, schedule_data):
        """Add a new schedule to the DB and register the job."""
        try:
            conn = get_db_connection(self.app)
            cursor = conn.execute(
                """INSERT INTO schedules
                   (name, schedule_type, playlist_id, song_id,
                    day_of_week, hour, minute, run_date,
                    start_date, end_date, duration_minutes, volume, enabled)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    schedule_data['name'],
                    schedule_data['schedule_type'],
                    schedule_data.get('playlist_id'),
                    schedule_data.get('song_id'),
                    schedule_data.get('day_of_week', ''),
                    schedule_data.get('hour', 0),
                    schedule_data.get('minute', 0),
                    schedule_data.get('run_date', ''),
                    schedule_data.get('start_date', ''),
                    schedule_data.get('end_date', ''),
                    schedule_data.get('duration_minutes', 35),
                    schedule_data.get('volume'),  # None = use default at runtime
                    schedule_data.get('enabled', 1),
                )
            )
            conn.commit()
            schedule_id = cursor.lastrowid

            # Fetch it back and register
            cursor = conn.execute(
                "SELECT * FROM schedules WHERE id = ?", (schedule_id,)
            )
            schedule = dict(cursor.fetchone())
            conn.close()
            self._register_job(schedule)
            return schedule_id
        except Exception as e:
            logger.error(f"Failed to add schedule: {e}")
            return None

    def update_schedule(self, schedule_id, schedule_data):
        """Update an existing schedule."""
        try:
            conn = get_db_connection(self.app)
            fields = []
            values = []
            for key in ['name', 'schedule_type', 'playlist_id', 'song_id',
                        'day_of_week', 'hour', 'minute', 'run_date',
                        'start_date', 'end_date', 'duration_minutes',
                        'volume', 'enabled']:
                if key in schedule_data:
                    fields.append(f"{key} = ?")
                    values.append(schedule_data[key])

            if not fields:
                conn.close()
                return False

            fields.append("updated_at = CURRENT_TIMESTAMP")
            values.append(schedule_id)

            conn.execute(
                f"UPDATE schedules SET {', '.join(fields)} WHERE id = ?",
                values
            )
            conn.commit()

            # Re-register job
            cursor = conn.execute(
                "SELECT * FROM schedules WHERE id = ?", (schedule_id,)
            )
            schedule = cursor.fetchone()
            conn.close()

            if schedule:
                schedule = dict(schedule)
                if schedule['enabled']:
                    self._register_job(schedule)
                else:
                    try:
                        self.scheduler.remove_job(f"schedule_{schedule_id}")
                    except Exception:
                        pass
            return True
        except Exception as e:
            logger.error(f"Failed to update schedule: {e}")
            return False

    def delete_schedule(self, schedule_id):
        """Delete a schedule."""
        try:
            # Remove APScheduler job
            try:
                self.scheduler.remove_job(f"schedule_{schedule_id}")
            except Exception:
                pass

            conn = get_db_connection(self.app)
            conn.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
            conn.commit()
            conn.close()
            logger.info(f"Deleted schedule {schedule_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete schedule: {e}")
            return False

    def get_all_schedules(self):
        """Get all schedules from the DB."""
        try:
            conn = get_db_connection(self.app)
            cursor = conn.execute(
                "SELECT * FROM schedules ORDER BY created_at DESC"
            )
            schedules = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return schedules
        except Exception as e:
            logger.error(f"Failed to get schedules: {e}")
            return []

    def get_upcoming_jobs(self, limit=10):
        """Get upcoming scheduled jobs."""
        jobs = self.scheduler.get_jobs()
        upcoming = []
        for job in jobs[:limit]:
            upcoming.append({
                'id': job.id,
                'name': job.name,
                'next_run': str(job.next_run_time) if job.next_run_time else None
            })
        return upcoming

    def shutdown(self):
        """Shutdown the scheduler."""
        self.scheduler.shutdown(wait=False)
        logger.info("Scheduler shutdown")
