from flask import Blueprint, current_app, g, jsonify, request

from ..models import speech_to_dict
from ..services.quality_service import QualityService
from ..services.speech_service import SpeechService
from .common import json_body, login_required

bp = Blueprint("speeches", __name__)


def _service():
    return SpeechService(g.db, current_app.config["TM"], current_app.extensions["analysis"], current_app.logger)


@bp.post("/speeches")
@login_required
def create_speech():
    return jsonify(speech_to_dict(_service().create(g.user, request.files.get("audio"), request.files.get("slides"),
                                                     request.form.get("slide_times"), request.form.get("speech_lang")))), 201


@bp.get("/speeches")
@login_required
def list_speeches():
    return jsonify([speech_to_dict(s) for s in _service().history(g.user)])


@bp.get("/speeches/<int:speech_id>")
@login_required
def get_speech(speech_id):
    return jsonify(speech_to_dict(_service().get(g.user, speech_id)))


@bp.delete("/speeches/<int:speech_id>")
@login_required
def delete_speech(speech_id):
    _service().delete(g.user, speech_id)
    return "", 204


@bp.get("/trainings")
@login_required
def trainings():
    return jsonify(_service().trainings(g.user))


@bp.get("/profile")
@login_required
def profile():
    return jsonify(_service().profile(g.user))


@bp.get("/recommendations")
@login_required
def recommendations():
    return jsonify([r.to_dict() for r in _service().user_recommendations(g.user)])


@bp.get("/stats")
@login_required
def stats():
    return jsonify(_service().stats(g.user))


def _quality():
    return QualityService(g.db, _service())


@bp.get("/speeches/<int:speech_id>/ratings")
@login_required
def list_ratings(speech_id):
    return jsonify([r.to_dict() for r in _quality().ratings(g.user, speech_id)])


@bp.put("/speeches/<int:speech_id>/ratings/<metric>")
@login_required
def rate_metric(speech_id, metric):
    return jsonify(_quality().rate(g.user, speech_id, metric, json_body()).to_dict())


@bp.put("/consent")
@login_required
def set_consent():
    return jsonify(_quality().set_consent(g.user, json_body()))
