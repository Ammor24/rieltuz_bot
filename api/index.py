from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot ishlayapti!"

@app.route("/api/index")
def test():
    return "OK"
