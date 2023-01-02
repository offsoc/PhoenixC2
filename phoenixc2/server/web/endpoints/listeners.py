from flask import Blueprint, jsonify, render_template, request

from phoenixc2.server.commander import Commander
from phoenixc2.server.database import ListenerModel, LogEntryModel, Session, UserModel
from phoenixc2.server.utils.misc import get_network_interfaces, get_platform
from phoenixc2.server.utils.ui import log
from phoenixc2.server.utils.web import generate_response

INVALID_ID = "Invalid ID."
LISTENER_DOES_NOT_EXIST = "Listener does not exist."
ENDPOINT = "listeners"


def listeners_bp(commander: Commander):
    listeners_bp = Blueprint(ENDPOINT, __name__, url_prefix="/listeners")

    @listeners_bp.route("/", methods=["GET"])
    @UserModel.authorized
    def get_listeners():
        use_json = request.args.get("json", "").lower() == "true"
        opened_listener = (
            Session.query(ListenerModel).filter_by(id=request.args.get("open")).first()
        )
        listener_types = ListenerModel.get_all_classes()
        listeners: list[ListenerModel] = Session.query(ListenerModel).all()
        if use_json:
            return jsonify([listener.to_dict(commander) for listener in listeners])
        return render_template(
            "listeners.j2",
            listeners=listeners,
            opened_listener=opened_listener,
            commander=commander,
            listener_types=listener_types,
            network_interfaces=get_network_interfaces(),
            platform=get_platform(),
        )

    @listeners_bp.route("/available", methods=["GET"])
    @UserModel.authorized
    def get_available():
        listeners = {}
        type = request.args.get("type")
        try:
            if type == "all" or type is None:
                for listener in ListenerModel.get_all_classes():
                    listeners[listener.name] = listener.to_dict(commander)
            else:
                listeners[type] = ListenerModel.get_class_from_type(type).to_dict(
                    commander
                )
        except Exception as e:
            return generate_response("danger", str(e), ENDPOINT, 400)
        else:
            return jsonify(listeners)

    @listeners_bp.route("/add", methods=["POST"])
    @UserModel.authorized
    def post_add():
        # Get request data
        use_json = request.args.get("json", "").lower() == "true"
        listener_type = request.form.get("type")
        name = request.form.get("name")
        is_interface = request.args.get("is_interface", "").lower() == "true"
        data = dict(request.form)
        if is_interface:
            interfaces = get_network_interfaces()
            if data.get("address", "") in interfaces:
                data["address"] = interfaces[data["address"]]
            else:
                return generate_response(
                    "danger", "Invalid network interface.", ENDPOINT, 400
                )
        try:
            # Check if data is valid and clean it
            data = ListenerModel.get_class_from_type(
                listener_type
            ).options.validate_all(data)
        except Exception as e:
            return generate_response("danger", str(e), ENDPOINT, 400)

        # Add listener
        try:
            # has to be added again bc it got filtered out by options.validate_data(data)
            data["type"] = listener_type
            listener = ListenerModel.add(data)
        except Exception as e:
            return generate_response("danger", str(e), ENDPOINT, 500)
        LogEntryModel.log(
            "success",
            "listeners",
            f"Added listener '{listener.name}' ({listener.type})",
            UserModel.get_current_user(),
        )
        if use_json:
            return (
                jsonify(
                    {
                        "status": "success",
                        "message": "Listener added successfully.",
                        "listener": listener.to_dict(commander),
                    }
                ),
                201,
            )
        return generate_response(
            "success", f"Created Listener {name} ({listener_type}).", ENDPOINT
        )

    @listeners_bp.route("/<int:id>/remove", methods=["DELETE"])
    @UserModel.authorized
    def delete_remove(id: int):
        # Get request data
        use_json = request.args.get("json", "").lower() == "true"
        stop = request.form.get("stop", "").lower() != "false"

        # Check if listener exists
        listener: ListenerModel = Session.query(ListenerModel).filter_by(id=id).first()
        if listener is None:
            return generate_response("danger", LISTENER_DOES_NOT_EXIST, ENDPOINT, 400)
        name = listener.name
        type = listener.type
        listener.delete(stop, commander)
        message = (
            f"Deleted and stopped listener '{name}' ({type})"
            if stop
            else f"Deleted listener '{name}' ({type})"
        )
        LogEntryModel.log(
            "success",
            "listeners",
            message,
            UserModel.get_current_user(),
        )
        if use_json:
            return jsonify(
                {
                    "status": "success",
                    "message": message,
                    "listener": listener.to_dict(commander),
                }
            )
        return generate_response("success", message, ENDPOINT)

    @listeners_bp.route("/edit", methods=["PUT", "POST"])
    @listeners_bp.route("/<int:id>/edit", methods=["PUT", "POST"])
    @UserModel.authorized
    def put_edit(id: int = None):
        # Get request data
        use_json = request.args.get("json", "").lower() == "true"
        form_data = dict(request.form)
        if id is None:
            if form_data.get("id") is None:
                return generate_response("danger", INVALID_ID, ENDPOINT, 400)
            id = int(form_data.get("id"))
            form_data.pop("id")

        # Check if listener exists
        listener: ListenerModel = Session.query(ListenerModel).filter_by(id=id).first()
        if listener is None:
            return generate_response("danger", LISTENER_DOES_NOT_EXIST, ENDPOINT, 400)

        # Edit listener
        try:
            listener.edit(form_data)
        except Exception as e:
            return generate_response("danger", str(e), ENDPOINT, 500)

        LogEntryModel.log(
            "success",
            "listeners",
            f"Edited listener '{listener.name}' ({listener.type})",
            UserModel.get_current_user(),
        )
        if use_json:
            return jsonify(
                {
                    "status": "success",
                    "message": "Listener edited successfully.",
                    "listener": listener.to_dict(commander),
                }
            )
        return generate_response(
            "success", f"Edited Listener {listener.name} ({listener.type}).", ENDPOINT
        )

    @listeners_bp.route("/<int:id>/start", methods=["POST"])
    @UserModel.authorized
    def post_start(id: int):
        # Check if listener exists
        listener: ListenerModel = Session.query(ListenerModel).filter_by(id=id).first()

        if listener is None:
            return generate_response("danger", LISTENER_DOES_NOT_EXIST, ENDPOINT, 400)

        log(
            f"({UserModel.get_current_user().username}) Starting Listener with ID {id}",
            "info",
        )

        try:
            status = listener.start(commander)
        except Exception as e:
            LogEntryModel.log(
                "danger",
                "listeners",
                status,
                UserModel.get_current_user(),
            )
            return generate_response("danger", str(e), ENDPOINT, 400)
        else:
            LogEntryModel.log(
                "success",
                "listeners",
                status,
                UserModel.get_current_user(),
            )
            return generate_response("success", status, ENDPOINT)

    @listeners_bp.route("/<int:id>/stop", methods=["POST"])
    @UserModel.authorized
    def post_stop(id: int):
        # Check if listener exists
        listener: ListenerModel = Session.query(ListenerModel).filter_by(id=id).first()

        if listener is None:
            return generate_response("danger", LISTENER_DOES_NOT_EXIST, ENDPOINT, 400)

        log(
            f"({UserModel.get_current_user().username}) Stopping Listener with ID {id}",
            "info",
        )

        try:
            listener.stop(commander)
        except Exception as e:
            return generate_response("danger", str(e), ENDPOINT, 500)
        else:
            LogEntryModel.log(
                "success",
                "listeners",
                f"Stopped listener '{listener.name}' ({listener.type})",
                UserModel.get_current_user(),
            )
            return generate_response(
                "success", f"Stopped Listener with ID {id}", ENDPOINT
            )

    @listeners_bp.route("/<int:id>/restart", methods=["POST"])
    @UserModel.authorized
    def post_restart(id: int):
        # Check if listener exists
        listener: ListenerModel = Session.query(ListenerModel).filter_by(id=id).first()

        try:
            log(
                f"({UserModel.get_current_user().username}) Restarting listener with ID {id}.",
                "info",
            )
            listener.restart(commander)
        except Exception as e:
            LogEntryModel.log(
                "danger",
                "listeners",
                f"Failed to restart listener '{listener.name}' ({listener.type}): {str(e)}",
                UserModel.get_current_user(),
            )
            return generate_response("danger", str(e), ENDPOINT, 500)
        else:
            LogEntryModel.log(
                "success",
                "listeners",
                f"Restarted listener '{listener.name}' ({listener.type})",
                UserModel.get_current_user(),
            )
            return generate_response(
                "success", f"Restarted listener with ID {id}", ENDPOINT
            )

    return listeners_bp
