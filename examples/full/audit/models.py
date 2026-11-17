"""django-pghistory's event models for a few models of the other apps.

Installed only on PostgreSQL (see settings.py). Triggers write an event for each insert
and update, whoever made it, and the admin's history panel lists them.
"""

import pghistory
from content.models import Post
from crm.models import Company, Deal
from helpdesk.models import Ticket
from taskmanager.models import Task

# A task's updated_at changes with each save, so it would show up in every event.
pghistory.track(app_label="audit", exclude=["updated_at"])(Task)
for model in (Company, Deal, Ticket, Post):
    pghistory.track(app_label="audit")(model)
