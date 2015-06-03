#!/usr/bin/env python2
#Copyright (c) 2015, Steven Smith (blha303)
#All rights reserved.
#
#Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
#
#1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
#
#2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
#
#THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

#Updates at https://github.com/blha303/question

from flask import Flask, request, jsonify, make_response
import json, requests, logging, time, jsondict, gzip, shortuuid

URL = "http://b303.me:7456"
app = Flask(__name__)

USERS = jsondict.JsonDict("users.json.gz", compress=True, autosave=True)
PENDING = jsondict.JsonDict("pending.json.gz", compress=True, autosave=True)
VERIFY = jsondict.JsonDict("verify.json.gz", compress=True, autosave=True)

@app.errorhandler(Exception)
def error_handler(e):
    try:
        code = e.code
    except AttributeError:
        code = 500
    return jsonify(error=code, text=str(e)), code

def gen_html(header, body=""):
    return "<center><h1>{}</h1><h2>{}</h2></center>".format(header, body)

def err_resp(json=True, **kwargs):
    response = jsonify(**kwargs) if json else make_response(**kwargs)
    response.status_code = kwargs["error"] if "error" in kwargs else 500
    return response

def airgram_check(email, id, msg="Hi! You've been added to Question. Swipe here to verify"):
    resp = requests.post("https://api.airgramapp.com/1/send_as_guest", data={'email': email, 'msg': msg, "url": URL + "/verify/" + id}, verify=False).json()
    return resp["status"] != "error", resp["error_msg"] if "error_msg" in resp else None

def airgram_send(**kwargs):
    resp = requests.post("https://api.airgramapp.com/1/send_as_guest", data=kwargs, verify=False).json()
    return resp["status"] != "error", resp["error_msg"] if "error_msg" in resp else None

@app.route("/verify/<id>")
def verify_id(id):
    global VERIFY
    global USERS
    if id in VERIFY and VERIFY[id] in USERS:
        USERS[VERIFY[id]]["verified"] = True
        del VERIFY[id]
        return gen_html("VERIFIED", "Feel free to close this page now :)")
    else:
        return err_resp(json=False, error=404, text=gen_html("NOT VERIFIED", "ID not found. Maybe you've already verified?"))

@app.route("/yes/<id>")
def yes(id):
    global PENDING
    global USERS
    if id in PENDING:
        airgram_send(email=USERS[PENDING[id]["from"]]["email"],
                     msg="{to} replied Yes to: {text}".format(**PENDING[id]))
        return gen_html("REPLY SENT")
    else:
        return err_resp(json=False, error=404, text=gen_html("ALREADY REPLIED"))

@app.route("/no/<id>")
def no(id):
    global PENDING
    global USERS
    if id in PENDING:
        airgram_send(email=USERS[PENDING[id]["from"]]["email"],
                     msg="{to} replied No to: {text}".format(**PENDING[id]))
        return gen_html("REPLY SENT")
    else:
        return err_resp(json=False, error=404, text=gen_html("ALREADY REPLIED"))


@app.route("/send/<nick>")
def send_question(nick):
    global USERS
    global PENDING
    if nick and 'text' in request.args and 'from' in request.args:
        if not request.args['from'] in USERS or not USERS.get(request.args['from'], {}).get('verified', False):
            reverify(request.args['from'])
            return err_resp(error=404, text="Source user not found or not yet verified (verification msg sent if exists)")
        if not nick in USERS or not USERS.get(nick, {}).get('verified', False):
            return err_resp(error=404, text="Destination user not found or not yet verified")
        id = shortuuid.uuid()
        PENDING[id] = {'to': nick, 'from': request.args['from'], 'text': request.args['text'], 'ts': time.time()}
        first, _f = airgram_send(email=USERS[nick]["email"], msg="Question from {} : No | {}".format(request.args["from"], request.args["text"]), url=URL + "/no/" + id)
        second, _s = airgram_send(email=USERS[nick]["email"], msg="Question from {} : Yes | {}".format(request.args["from"], request.args["text"]), url=URL + "/yes/" + id)
        if first and second:
            return jsonify(status="ok")
        elif (first and not second) or (second and not first):
            _ = airgram_send(email=USERS[nick]["email"], msg="Oops! Can't send {} message. Please contact {} ASAP.".format("NO" if second else "YES", request.args['from']))
            return err_resp(error=504, text="{} message didn't send, please contact {} directly (they may be contacting you also)".format("First" if second else "Second", nick))
        else:
            return err_resp(error=504, text="Messages could not be sent, please notify blha303 at b3@blha303.com.au and contact {} directly at {}".format(nick, USERS[nick]["email"]))


@app.route("/add/<nick>")
def add_user(nick):
    global VERIFY
    global USERS
    if nick and nick in USERS:
        return err_resp(error=409, text="Username in use")
    if len(nick) > 20:
        return err_resp(error=400, text="Username is too long (>20)")
    elif 'email' in request.args:
        id = shortuuid.uuid()
        VERIFY[id] = nick
        exists, err = airgram_check(request.args['email'], id)
        if exists:
            USERS[nick] = {'email': request.args["email"], 'verified': False, 'reg': time.time()}
            return jsonify(status="ok")
        else:
            return err_resp(error=404, text="{} airgramapp.com".format(err))
    else:
        return err_resp(error=400, text="Invalid or missing email address")

@app.route("/reverify/<nick>")
def reverify(nick):
    id = shortuuid.uuid()
    VERIFY[id] = nick
    if airgram_check(USERS[nick]["email"], id, msg="Please reverify your Airgram account for Question. Swipe here to verify"):
        return jsonify(status="ok")
    else:
        return err_resp(error=404, text="An error occured while verifying your Airgram account.")

@app.route("/user/<nick>")
def user_lookup(nick):
    if nick and nick in USERS:
        return jsonify({nick: USERS[nick]})
    else:
        return err_resp(error=404, text="User not found")

if __name__ == "__main__":
    app.run(port=7456, host="0.0.0.0")
