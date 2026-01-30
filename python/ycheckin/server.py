import flask
import pathlib
import scrapy


app = flask.Flask(__name__)


@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"

class SignupGeniusSpider(scrapy.Spider):

    ymca_signup_url = "https://www.signupgenius.com/go/10C0B4BA4AC29AAF9CF8-49049901-adult#/"

    async def start(self):
        return scrapy.Request(url="https://www.signupgenius.com/", callback=self.parse)
    
    def parse(self, response):
