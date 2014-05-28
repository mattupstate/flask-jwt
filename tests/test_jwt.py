# -*- coding: utf-8 -*-
"""
    tests.test_jwt
    ~~~~~~~~~~~~~~

    Flask-JWT tests
"""
import time

from flask import Flask, json

import flask_jwt


def assert_error_response(r, code, msg, desc):
    jdata = json.loads(r.data)
    assert r.status_code == code
    assert jdata['status_code'] == code
    assert jdata['error'] == msg
    assert jdata['description'] == desc


def test_initialize():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'super-secret'
    jwt = flask_jwt.JWT(app)
    assert isinstance(jwt, flask_jwt.JWT)
    assert len(app.url_map._rules) == 2


def test_adds_auth_endpoint():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'super-secret'
    app.config['JWT_AUTH_URL_RULE'] = '/auth'
    app.config['JWT_AUTH_ENDPOINT'] = 'jwt_auth'
    flask_jwt.JWT(app)
    rules = [str(r) for r in app.url_map._rules]
    assert '/auth' in rules


def test_auth_endpoint_with_valid_request(client):
    r = client.post(
        '/auth',
        headers={'content-type': 'application/json'},
        data=json.dumps({
            'username': 'joe',
            'password': 'pass'
        }))
    assert r.status_code == 200
    assert 'token' in json.loads(r.data)


def test_auth_endpoint_with_invalid_request(client):
    # Invalid request
    r = client.post(
        '/auth',
        headers={'content-type': 'application/json'},
        data=json.dumps({
            'username': 'joe'
        }))
    assert r.status_code == 400
    jdata = json.loads(r.data)
    assert 'error' in jdata
    assert jdata['error'] == 'Bad Request'
    assert 'description' in jdata
    assert jdata['description'] == 'Missing required credentials'
    assert 'status_code' in jdata
    assert jdata['status_code'] == 400


def test_auth_endpoint_with_invalid_credentials(client):
    r = client.post(
        '/auth',
        headers={'content-type': 'application/json'},
        data=json.dumps({
            'username': 'bogus',
            'password': 'bogus'
        }))
    assert r.status_code == 403
    jdata = json.loads(r.data)
    assert 'error' in jdata
    assert jdata['error'] == 'Forbidden'
    assert 'description' in jdata
    assert jdata['description'] == 'Invalid credentials'
    assert 'status_code' in jdata
    assert jdata['status_code'] == 403


def test_jwt_required_decorator_with_valid_token(app, client):
    r = client.post(
        '/auth',
        headers={'content-type': 'application/json'},
        data=json.dumps({
            'username': 'joe',
            'password': 'pass'
        }))

    jdata = json.loads(r.data)
    token = jdata['token']

    r = client.get(
        '/protected',
        headers={'authorization': 'Bearer ' + token})
    assert r.status_code == 200
    assert r.data == b'success'


def test_jwt_required_decorator_with_valid_request_current_user(app, client):
    with client as c:
        r = c.post(
            '/auth',
            headers={'content-type': 'application/json'},
            data=json.dumps({
                'username': 'joe',
                'password': 'pass'
            }))

        jdata = json.loads(r.data)
        token = jdata['token']

        r = c.get(
            '/protected',
            headers={'authorization': 'Bearer ' + token})
        assert flask_jwt.current_user


def test_jwt_required_decorator_with_invalid_request_current_user(app, client):
    with client as c:
        r = c.get(
            '/protected',
            headers={'authorization': 'Bearer bogus'})
        assert not flask_jwt.current_user


def test_jwt_required_decorator_with_invalid_authorization_headers(app, client):
    # Missing authorization header
    r = client.get('/protected')
    assert_error_response(r, 401, 'Authorization Required', 'Authorization header was missing')
    assert r.headers['WWW-Authenticate'] == 'JWT realm="Login Required"'

    # Not a bearer token
    r = client.get('/protected', headers={'authorization': 'Bogus xxx'})
    assert_error_response(r, 400, 'Invalid JWT header', 'Unsupported authorization type')

    # Missing token
    r = client.get('/protected', headers={'authorization': 'Bearer'})
    assert_error_response(r, 400, 'Invalid JWT header', 'Token missing')

    # Token with spaces
    r = client.get('/protected', headers={'authorization': 'Bearer xxx xxx'})
    assert_error_response(r, 400, 'Invalid JWT header', 'Token contains spaces')


def test_jwt_required_decorator_with_invalid_jwt_tokens(client):
    r = client.post(
        '/auth',
        headers={'content-type': 'application/json'},
        data=json.dumps({
            'username': 'joe',
            'password': 'pass'
        }))

    jdata = json.loads(r.data)
    token = jdata['token']

    # Undecipherable
    r = client.get('/protected', headers={'authorization': 'Bearer %sX' % token})
    assert_error_response(r, 400, 'Invalid JWT', 'Token is undecipherable')

    # Expired
    time.sleep(1.5)
    r = client.get('/protected', headers={'authorization': 'Bearer ' + token})
    assert_error_response(r, 400, 'Invalid JWT', 'Token is expired')


def test_jwt_required_decorator_with_missing_user(client, jwt):
    r = client.post(
        '/auth',
        headers={'content-type': 'application/json'},
        data=json.dumps({
            'username': 'joe',
            'password': 'pass'
        }))

    jdata = json.loads(r.data)
    token = jdata['token']

    @jwt.user_handler
    def load_user(payload):
        return None

    r = client.get('/protected', headers={'authorization': 'Bearer %s' % token})
    assert_error_response(r, 400, 'Invalid JWT', 'User does not exist')


def test_custom_error_handler(client, jwt):
    @jwt.error_handler
    def error_handler(e):
        return "custom"

    r = client.get('/protected')
    assert r.data == b'custom'
