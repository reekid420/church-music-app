"""Page view routes."""

from flask import Blueprint, render_template

views_bp = Blueprint('views', __name__)


@views_bp.route('/')
def dashboard():
    """Main dashboard page."""
    return render_template('dashboard.html')


@views_bp.route('/library')
def library():
    """Music library page."""
    return render_template('library.html')


@views_bp.route('/schedules')
def schedules():
    """Schedule manager page."""
    return render_template('schedules.html')


@views_bp.route('/speakers')
def speakers():
    """Speaker manager page."""
    return render_template('speakers.html')


@views_bp.route('/settings')
def settings():
    """Settings page."""
    return render_template('settings.html')
