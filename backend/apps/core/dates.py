"""Dates as people in Saudi Arabia see them. We store UTC but licences expire on Riyadh dates."""

from datetime import date
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone


def riyadh_today() -> date:
    return timezone.now().astimezone(ZoneInfo(settings.DISPLAY_TIME_ZONE)).date()
