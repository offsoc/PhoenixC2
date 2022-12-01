import tempfile

from flask import Blueprint, jsonify, render_template, request, send_file

from phoenix_framework.server.commander import Commander
from phoenix_framework.server.database import (
    ListenerModel,
    LogEntryModel,
    Session,
    StagerModel,
)
from phoenix_framework.server.utils.web import (
    authorized,
    generate_response,
    get_current_user,
)

INVALID_ID = "Invalid ID."
STAGER_DOES_NOT_EXIST = "Stager does not exist."
ENDPOINT = "stagers"


def stagers_bp(commander: Commander):

    stagers_bp = Blueprint(ENDPOINT, __name__, url_prefix="/stagers")

    @stagers_bp.route("/", methods=["GET"])
    @authorized
    def get_stagers():
        use_json = request.args.get("json", "") == "true"
        stager_query = Session.query(StagerModel)
        stagers: list[StagerModel] = stager_query.all()
        stager_types = StagerModel.get_all_classes()
        listeners: list[ListenerModel] = Session.query(ListenerModel).all()
        if use_json:
            return jsonify([stager.to_dict(commander) for stager in stagers])
        opened_stager = stager_query.filter_by(id=request.args.get("open")).first()
        return render_template(
            "stagers.j2",
            stagers=stagers,
            opened_stager=opened_stager,
            commander=commander,
            listeners=listeners,
            stager_types=stager_types,
        )

    @stagers_bp.route("/available", methods=["GET"])
    @authorized
    def get_available():
        stagers = {}
        type = request.args.get("type")
        try:
            if type == "all" or type is None:
                for stager in StagerModel.get_all_classes():
                    stagers[stager.name] = stager.to_dict(commander)
            else:
                stagers[type] = StagerModel.get_class_from_type(type).to_dict(commander)
        except Exception as e:
            return generate_response("danger", str(e), ENDPOINT, 400)

        else:
            return jsonify(stagers)

    @stagers_bp.route("/add", methods=["POST"])
    @authorized
    def post_add():
        # Get request data
        use_json = request.args.get("json", "").lower() == "true"
        name = request.form.get("name")
        data = dict(request.form)
        try:
            # check if name is okay
            if not name:
                raise ValueError("Name is required.")

            # check if stager name is already taken
            if Session.query(StagerModel).filter_by(name=name).first():
                raise ValueError("Stager name is already taken.")

            # check if listener exists
            listener: ListenerModel = (
                Session.query(ListenerModel).filter_by(id=data.get("listener")).first()
            )

            if listener is None:
                raise ValueError("Listener does not exist.")

            # Check if data is valid and clean it
            stager_class = StagerModel.get_class_from_type(listener.type)
            data = stager_class.options.validate_all(data)
        except Exception as e:
            return generate_response("danger", str(e), ENDPOINT, 400)

        # Add stager
        try:
            stager = StagerModel.add(data, Session)
        except Exception as e:
            return generate_response("danger", str(e), ENDPOINT, 500)

        LogEntryModel.log(
            "success",
            "stagers",
            f"Created stager '{stager.name}' from Listener '{listener.name}'.",
            Session,
            get_current_user(),
        )
        if use_json:
            return (
                jsonify(
                    {
                        "status": "success",
                        "message": "Stager created successfully.",
                        "stager": stager.to_dict(commander),
                    }
                ),
                201,
            )
        return generate_response(
            "success", f"Successfully created stager '{name}'.", ENDPOINT
        )

    @stagers_bp.route("/<int:id>/remove", methods=["DELETE"])
    @authorized
    def delete_remove(id: int):
        # Check if Stager exists
        stager: StagerModel = Session.query(StagerModel).filter_by(id=id).first()

        if stager is None:
            return generate_response("danger", STAGER_DOES_NOT_EXIST, ENDPOINT, 400)

        # set listener name because we need it after the stager is deleted
        listener_name = stager.listener.name
        Session().delete(stager)
        Session().commit()

        LogEntryModel.log(
            "success",
            "stagers",
            f"Deleted stager '{stager.name}' from Listener '{listener_name}'",
            Session,
            get_current_user(),
        )
        return generate_response("success", f"Deleted Stager with ID {id}.", ENDPOINT)

    @stagers_bp.route("/edit", methods=["PUT", "POST"])
    @stagers_bp.route("/<int:id>/edit", methods=["PUT", "POST"])
    @authorized
    def put_edit(id: int = None):
        # Get request data
        form_data = dict(request.form)
        if id is None:
            if form_data.get("id") is None:
                return generate_response("danger", INVALID_ID, ENDPOINT, 400)
            id = int(form_data.get("id"))
            form_data.pop("id")

        # Check if stager exists
        stager: StagerModel = Session.query(StagerModel).filter_by(id=id).first()
        if stager is None:
            return generate_response("danger", STAGER_DOES_NOT_EXIST, ENDPOINT, 400)

        # Edit stager
        try:
            stager.edit(form_data)
            Session.commit()
        except Exception as e:
            return generate_response("danger", str(e), ENDPOINT, 500)

        LogEntryModel.log(
            "success",
            "stagers",
            f"Edited stager '{stager.name}'",
            Session,
            get_current_user(),
        )
        return generate_response("success", f"Edited stager with ID {id}.", ENDPOINT)

    @stagers_bp.route("/<int:id>/download", methods=["GET"])
    def get_download(id: int):
        # Get Request Data
        use_json = request.args.get("json", "").lower() == "true"
        one_liner = request.args.get("one_liner", "") == "true"

        # Check if Stager exists
        stager_db: StagerModel = Session.query(StagerModel).filter_by(id=id).first()
        if stager_db is None:
            return generate_response("danger", STAGER_DOES_NOT_EXIST, ENDPOINT, 400)

        # Get Stager
        try:
            final_payload = stager_db.stager_class.generate(stager_db, one_liner)
        except Exception as e:
            return generate_response("danger", str(e), ENDPOINT, 500)
        else:
            if use_json:
                return jsonify({"status": "success", "stager": final_payload.output})
            elif final_payload.payload.compiled:
                return send_file(
                    final_payload.output,
                    as_attachment=True,
                    download_name=final_payload.name,
                )
            else:
                tmp = tempfile.TemporaryFile()
                tmp.write(final_payload.output.encode())
                tmp.seek(0)
                return send_file(
                    tmp, as_attachment=True, download_name=final_payload.name
                )

    return stagers_bp
