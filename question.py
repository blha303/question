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

def err_resp(json=True, **kwargs):
    response = jsonify(**kwargs) if json else make_response(**kwargs)
    response.status_code = kwargs["error"] if "error" in kwargs else 500
    return response

def airgram_check(email, id):
    resp = requests.post("https://api.airgramapp.com/1/send_as_guest", data={'email': email, 'msg': "Hi! You've been added to Question. Swipe here to verify", "url": URL + "/verify/" + id}, verify=False).json()
    return resp["status"] != "ok", resp

def airgram_send(**kwargs):
    resp = requests.post("https://api.airgramapp.com/1/send_as_guest", data=kwargs, verify=False).json()
    return resp["status"] == "ok", resp


@app.route("/verify/<id>")
def verify_id(id):
    global VERIFY
    global USERS
    if id in VERIFY and VERIFY[id] in USERS:
        USERS[VERIFY[id]]["verified"] = True
        del VERIFY[id]
        return make_response("<center><h1>VERIFIED</h1><h2>Feel free to close this window now</h2></center>")
    else:
        return err_resp(json=False, error=404, text="<center><h1>NOT VERIFIED</h1><h2>ID not found. Maybe you've already verified?</h2></center>")

@app.route("/send/<nick>")
def send_question(nick):
    global USERS
    global PENDING
    if nick and 'text' in request.args and 'from' in request.args:
        if not nick in USERS or not USERS.get(nick, {}).get('verified', False):
            return err_resp(error=404, text="Destination user not found or not yet verified")
        if not request.args['from'] in USERS or not USERS.get(request.args['from'], {}).get('verified', False):
            return err_resp(error=404, text="Source user not found or not yet verified")
        id = shortuuid.uuid()
        PENDING[id] = {'to': nick, 'from': request.args['from'], 'text': request.args['text'], 'ts': time.time()}
        first, _f = airgram_send(email=USERS[nick]["email"], msg="Question from {from} : Yes | {text}".format(**request.args), url=URL + "/yes/" + id)
        second, _s = airgram_send(email=USERS[nick]["email"], msg="Question from {from} : Yes | {text}".format(**request.args), url=URL + "/no/" + id)
        if first and second:
            return jsonify(status="ok")
        elif (first and not second) or (second and not first):
            _ = airgram_send(email=USERS[nick]["email"], msg="Oops! Can't send {} message. Please contact {} ASAP.".format("first" if second else "second", request.args['from']))
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
        if airgram_check(request.args['email'], id):
            USERS[nick] = {'email': request.args["email"], 'verified': False, 'reg': time.time()}
            return jsonify(status="ok")
        else:
            return err_resp(error=404, text="No Airgram account for specified email address, please create account at airgramapp.com")
    else:
        return err_resp(error=400, text="Invalid or missing email address")

@app.route("/reverify/<nick>")
def reverify(nick):
    id = shortuuid.uuid()
    VERIFY[id] = nick
    if airgram_check(USERS[nick]["email"], id):
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
