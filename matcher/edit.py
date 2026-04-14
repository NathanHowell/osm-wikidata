"""Save edits."""

import html

import requests
from flask import g

from . import database, mail, osm_oauth, user_agent_headers
from .database import db
from .model import Changeset

really_save = True
osm_api_base = "https://api.openstreetmap.org/api/0.6"


def new_changeset(comment: str, extra_tags: dict[str, str] | None = None) -> str:
    """XML string for a new changeset with the given comment and optional extra tags."""
    tag_lines = [
        '    <tag k="created_by" v="https://osm.wikidata.link/"/>',
        f'    <tag k="comment" v="{html.escape(comment)}"/>',
    ]
    for k, v in (extra_tags or {}).items():
        if v:
            tag_lines.append(f'    <tag k="{html.escape(k)}" v="{html.escape(v)}"/>')
    tags = "\n".join(tag_lines)
    return f"<osm>\n  <changeset>\n{tags}\n  </changeset>\n</osm>"


def osm_request(path: str, **kwargs: dict):
    """Make an authenticated request to the OSM API."""
    return osm_oauth.api_put_request(path, **kwargs)


def create_changeset(changeset: str):
    """Call the OSM API method to create a new changeset."""
    try:
        return osm_request("/changeset/create", data=changeset.encode("utf-8"))
    except requests.exceptions.HTTPError as r:
        print(changeset)
        print(r.response.text)
        raise


def close_changeset(changeset_id: int) -> requests.Response:
    """Send a request to the OSM API to close a changeset."""
    return osm_request(f"/changeset/{changeset_id}/close")


def save_element(osm_type, osm_id, element_data) -> requests.Response | None:
    """Update an OSM object and check for errors."""
    osm_path = f"/{osm_type}/{osm_id}"
    r = osm_request(osm_path, data=element_data)
    reply = r.text.strip()
    if reply.isdigit():
        return r

    subject = f"matcher error saving element: {osm_path}"
    username = g.user.username
    body = f"""
https://www.openstreetmap.org{osm_path}

user: {username}
message user: https://www.openstreetmap.org/message/new/{username}

error:
{reply}
"""

    mail.send_mail(subject, body)

    return None


def record_changeset(**kwargs: dict) -> Changeset:
    """Save a changeset in the database."""
    change = Changeset(created=database.now_utc(), user=g.user, **kwargs)

    db.session.add(change)
    db.session.commit()

    return change


def get_existing(osm_type: str, osm_id: int) -> requests.Response:
    """Get existing OSM object using the OSM API."""
    url = "{}/{}/{}".format(osm_api_base, osm_type, osm_id)
    return requests.get(url, headers=user_agent_headers())
