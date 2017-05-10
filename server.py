#!/usr/bin/env python

import os
import uuid

from flask import Flask
from flask import request
from kai.parser.parser import Parser
from kai.sl.json_serialiser import JsonSystem
from kai.configuration import get_section_dict
from kai.cassandra.cluster import Cassandra, set_cassy
import kai.sl.ask
import kai.sl.teach
from kai.sl.user import get_session_from_session_id, create_user, sign_in, sign_out

import json

# setup cassandra from configuration
configuration_file = os.path.join(os.path.dirname(__file__), 'settings.ini')
cassandra_config = get_section_dict(configuration_file, 'Cassandra')
set_cassy(Cassandra(cassandra_config))
# get security settings
security_config = get_section_dict(configuration_file, 'Security')
min_password_length = int(security_config['min_password_length'])


app = Flask(__name__)
parser = Parser()


# return an error rmessage with result code
def return_error(error_str: str, status: int =500):
    return app.response_class(
        response=json.dumps({'error': error_str}),
        status=status,
        mimetype='application/json')


# return any json
def return_json(obj, status: int =200):
    return app.response_class(
        response=json.dumps(obj, cls=JsonSystem),
        status=status,
        mimetype='application/json')


# return general msg
def return_msg(text: str, status: int =200):
    return app.response_class(
        response=json.dumps({'information': text}),
        status=status,
        mimetype='application/json')


#########################################################################################
# sl parsing

# curl -H "Content-Type: plain/text" -X POST --data @file.txt http://localhost:5000/api/parser
@app.route('/sl/parse', methods=['GET', 'POST'])
def sl_parse():
    text = request.args['text']
    if len(text) == 0:
        text = request.data.decode('utf-8')  # body text to ask
    if len(text.strip()) > 0:
        sentence_list = parser.parse_document(text)
        return return_json(sentence_list)
    else:
        return return_error('text missing / empty')


@app.route('/sl/parse-to-png', methods=['GET'])
def sl_parse_to_png():
    text = request.args['text']
    if len(text) == 0:
        text = request.data.decode('utf-8')  # body text to ask
    if len(text.strip()) > 0:
        return return_error("todo: implement properly")
    else:
        return return_error('text missing / empty')


#########################################################################################
## teach/ask API

# ask a question, expectes session_id as a query parameter
@app.route('/ask', methods=['POST'])
def ask():
    session_id_str = request.args['session_id']
    if len(session_id_str) > 0:
        text = request.data.decode('utf-8')  # body text to ask
        session = get_session_from_session_id(uuid.UUID("{" + session_id_str + "}"))
        if session is not None:
            result_list, err_str = kai.sl.ask.ask(session, text)
            if len(err_str) == 0:
                return return_json(result_list)
            else:
                return return_error(err_str)
        else:
            return return_error("invalid session")
    else:
        return return_error("invalid request, session_id query parameter missing")


# teach a new fact
@app.route('/teach', methods=['POST'])
def teach():
    session_id_str = request.args['session_id']
    if len(session_id_str) > 0:
        text = request.data.decode('utf-8')  # body text to ask
        session = get_session_from_session_id(uuid.UUID("{" + session_id_str + "}"))
        if session is not None:
            result_str = kai.sl.teach.teach(session, text)
            if result_str.startswith("ok, "):
                return return_msg(result_str)
            else:
                return return_error(result_str)
        else:
            return return_error("invalid session")
    else:
        return return_error("invalid request, session_id query parameter missing")


# remove a previously taught fact
@app.route('/remove/factoid/<id>', methods=['DELETE'])
def remove_factoid(id: str):
    session_id_str = request.args['session_id']
    if len(session_id_str) > 0 and len(id) > 0:
        text = request.data.decode('utf-8')  # body text to ask
        session = get_session_from_session_id(uuid.UUID("{" + session_id_str + "}"))
        factoid_id = uuid.UUID("{" + id + "}")
        if session is not None:
            return return_msg(kai.sl.teach.delete_token_list(factoid_id, session.get_username()))
        else:
            return return_error("invalid session")
    else:
        return return_error("invalid request, session_id query parameter missing")


#########################################################################################
# user manager

# create a new user account
@app.route('/user/create', methods=['POST'])
def user_create():
    json_dict = json.loads(request.data.decode('utf-8'))
    if "first_name" in json_dict and "surname" in json_dict and "email" in json_dict and "password" in json_dict:
        user, err_str = create_user(json_dict['email'], json_dict['first_name'], json_dict['surname'], json_dict['password'], min_password_length)
        if len(err_str) == 0:
            return return_msg("user created")
        else:
            return return_error(err_str)
    else:
        return return_error("invalid paramters in /user/create, user object.")


# sign in an existing user
@app.route('/user/signin', methods=['POST'])
def user_signin():
    json_dict = json.loads(request.data.decode('utf-8'))
    if json_dict and "email" in json_dict and "password" in json_dict:
        session, err_str = sign_in(json_dict['email'], json_dict['password'], min_password_length)
        if len(err_str) == 0:
            return return_json(session)
        else:
            return return_error(err_str)
    else:
        return return_error("invalid paramters in /user/signin, user details.")


# sign out an existing user
@app.route('/user/signout', methods=['GET'])
def user_signout():
    session_id_str = request.args['session_id']
    if len(session_id_str) > 0:
        sign_out(uuid.UUID("{" + session_id_str + "}"))
        return return_msg("logged out")
    else:
        return return_error("invalid paramters in /user/signout, session id missing.")


#########################################################################################

if __name__ == '__main__':
    app.run()
