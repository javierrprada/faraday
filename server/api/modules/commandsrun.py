# Faraday Penetration Test IDE
# Copyright (C) 2016  Infobyte LLC (http://www.infobytesec.com/)
# See the file 'doc/LICENSE' for the license information
import time

import datetime
from flask import Blueprint
from flask_classful import route
from marshmallow import fields, post_load

from server.api.base import AutoSchema, ReadWriteWorkspacedView, PaginatedMixin
from server.models import Command, Workspace
from server.schemas import MutableField, PrimaryKeyRelatedField

commandsrun_api = Blueprint('commandsrun_api', __name__)


class CommandSchema(AutoSchema):
    _id = fields.Integer(dump_only=True, attribute='id')
    itime = fields.Method(serialize='get_itime', deserialize='load_itime', required=True, attribute='start_date')
    duration = MutableField(
        fields.Method(serialize='get_duration'),
        fields.Integer(),
        allow_none=True)
    workspace = PrimaryKeyRelatedField('name', dump_only=True)

    def load_itime(self, value):
        return datetime.datetime.fromtimestamp(value)

    def get_itime(self, obj):
        return time.mktime(obj.start_date.utctimetuple()) * 1000

    def get_duration(self, obj):
        if obj.end_date and obj.start_date:
            return (obj.end_date - obj.start_date).seconds + ((obj.end_date - obj.start_date).microseconds / 1000000.0)
        if obj.start_date and not obj.end_date:
            return 'In progress'
        if not obj.start_date and not obj.end_date:
            return 'Not started'

    @post_load
    def post_load_set_end_date_with_duration(self, data):
        # there is a potential bug when updating, the start_date can be changed.
        duration = data.pop('duration', None)
        if duration:
            data['end_date'] = data['start_date'] + datetime.timedelta(
                seconds=duration)

    class Meta:
        model = Command
        fields = ('_id', 'command', 'duration', 'itime', 'ip', 'hostname',
                  'params', 'user', 'workspace', 'tool', 'import_source')


class CommandView(PaginatedMixin, ReadWriteWorkspacedView):
    route_base = 'commands'
    model_class = Command
    schema_class = CommandSchema
    get_joinedloads = [Command.workspace]
    order_field = Command.start_date.desc()

    def _envelope_list(self, objects, pagination_metadata=None):
        commands = []
        for command in objects:
            commands.append({
                'id': command['_id'],
                'key': command['_id'],
                'value': command
            })
        return {
            'commands': commands,
        }

    @route('/activity_feed/')
    def activity_feed(self, workspace_name):
        res = []
        query = Command.query.join(Workspace).filter_by(name=workspace_name)
        for command in query.all():
            res.append({
                '_id': command.id,
                'user': command.user,
                'import_source': command.import_source,
                'command': command.command,
                'tool': command.tool,
                'params': command.params,
                'vulnerabilities_count': (command.sum_created_vulnerabilities or 0),
                'hosts_count': command.sum_created_hosts or 0,
                'services_count': command.sum_created_services or 0,
                'criticalIssue': command.sum_created_vulnerability_critical or 0,
                'date': time.mktime(command.start_date.timetuple()) * 1000,
            })
        return res

CommandView.register(commandsrun_api)
