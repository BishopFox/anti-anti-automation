#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import logging
import re
import cgi
import json
import urllib2
import HTMLParser
import webapp2

from types import *
from google.appengine.ext.webapp.mail_handlers import InboundMailHandler
from google.appengine.api import urlfetch


class MainHandler(webapp2.RequestHandler):
    def get(self):
        self.response.write('Hello world!')


class RegisterMe():
    def __init__(self):
        return

    def mailgrep(self, body):
        # Do not submit all links only activation links are useful in this case
        # should be modified to fit your needs currently supports urls with signup confirm verify and activate.
        activation_url = re.findall('(https?://[^\s<"]+(?:signup|confirm|verify|activate)[^\s<"]+)', body)
        if activation_url:
            html_parser = HTMLParser.HTMLParser()
            #remove html encoding from url
            activation_url = [urllib2.unquote(html_parser.unescape(url)) for url in activation_url]
            logging.info("Activation URL: " + ', '.join(activation_url))
            #return only the first activation link
            return activation_url[0]
        logging.info("No Activation URL Found")
        return ""

    def activate(self, from_email, from_name, email, subject, text, html):
        # Some emails contain text/html some contain text/plain they should both be decoded by this point so we merge them to grep through the whole thing
        body = html + text
        activation_url = self.mailgrep(body)
        if activation_url:
            activation_response = urlfetch.fetch(url=activation_url, follow_redirects=True)
            if activation_response.status_code == 200 or activation_response.status_code == 302:
                logging.info("Activation URL successfully requested")
                # In most cases this code is all that is required to successfully activate an account.
                # In some cases registration is more complex than just requesting an activation URL.
                # Sometimes you have to submit your credentials
                # Sometimes there is a CSRF token
                # Sometimes it automatically logs you into the application
                # Or you want to send a notification to yourself on success
                # Here is an example of making additional request based on email sender
                # if from_email == 'thank.you.for.registerting@some.domain.com':
                #     make some other request to finish activation of some.domain.com
                # elif from_email == "thank.you.for.registering.with.us.instead.of.some.domain.com@obviously.the.cooler.domain.com":
                #     make some specific request to activate account on obviously.the.cooler.domain.com
                return True
            logging.error("Activation Failed")
        return False


#Handle emails directly sent to *@YourAppID.appspotmail.com
class LogSenderHandler(InboundMailHandler):
    def receive(self, mail_message):
        #extract all values from the mail_message
        subject = mail_message.subject
        sender = mail_message.sender
        email = mail_message.to
        time = mail_message.date

        name_list = re.findall("^([^<]+)", sender)
        if name_list:
            from_name = name_list[0]
        else:
            from_name = ""

        email_list = re.findall("^[^<]+<([^>]+)", sender)
        if email_list:
            from_email = email_list[0]
        else:
            from_email = ""

        #Get email body content
        html = ''
        text = ''
        html_parser = HTMLParser.HTMLParser()

        html_bodies = mail_message.bodies('text/html')
        for content_type, body in html_bodies:
            html = html_parser.unescape(body.decode())

        html_bodies = mail_message.bodies('text/plain')
        for content_type, body in html_bodies:
            text = html_parser.unescape(body.decode())

        #Log all extracted information
        logging.info("Received a message time: " + time)
        logging.info("Received a message sender: " + sender)
        logging.info("Received a message from_email: " + from_email)
        logging.info("Received a message from_name: " + from_name)
        logging.info("Received a message subject: " + subject)
        logging.info("Received a message to email: " + email)
        logging.info("Received a message html: " + html.encode('utf-8'))
        logging.info("Received a message text: " + text.encode('utf-8'))

        #Identify and request any identified activation links
        register = RegisterMe()
        registered = "Registered: {}".format(register.activate(from_email, from_name, email, subject, text, html))

        logging.info("Successful: " + str(registered))


#Handle mail in the form of a json object sent in a post request
class Mandrill(webapp2.RequestHandler):
    #Mandrill makes a head request to make sure this path exists
    def head(self):
        return

    def post(self):
        data = cgi.escape(self.request.get('mandrill_events'))
        logging.info("RAW")
        logging.info(type(data))
        data = json.loads(data)
        logging.info("JSON.loads")
        logging.info(type(data))
        logging.info("size=" + str(len(data)))
        if not type(data) is ListType:
            self.response.write("Expected List Received: " + str(type(data)))
            return
        for jsonobject in data:
            #make sure we are dealing with a json object
            if not type(jsonobject) is DictType:
                continue
            logging.info("SubSectionType=" + str(type(jsonobject)))
            logging.info("SubSectionSize=" + str(len(jsonobject)))
            time = ''
            text = ''
            from_email = ''
            from_name = ''
            to = ''
            subject = ''
            sender = ''
            html = ''
            email = ''

            #extract all useful values from email json object
            if jsonobject:
                if 'ts' in jsonobject and jsonobject['ts']:
                    time = str(jsonobject['ts'])
                if 'msg' in jsonobject:
                    if 'text' in jsonobject['msg'] and jsonobject['msg']['text']:
                        text = jsonobject['msg']['text']
                    if 'from_email' in jsonobject['msg'] and jsonobject['msg']['from_email']:
                        from_email = jsonobject['msg']['from_email']
                    if 'from_name' in jsonobject['msg'] and jsonobject['msg']['from_name']:
                        from_name = jsonobject['msg']['from_name']
                    if 'to' in jsonobject['msg'] and jsonobject['msg']['to']:
                        to = jsonobject['msg']['to']
                    if 'subject' in jsonobject['msg'] and jsonobject['msg']['subject']:
                        subject = jsonobject['msg']['subject']
                    if 'sender' in jsonobject['msg'] and jsonobject['msg']['sender']:
                        sender = jsonobject['msg']['sender']
                    if 'html' in jsonobject['msg'] and jsonobject['msg']['html']:
                        html = jsonobject['msg']['html']
                    if 'email' in jsonobject['msg'] and jsonobject['msg']['email']:
                        email = jsonobject['msg']['email']

            #Log all extracted information
            logging.info("Received a message time: " + time)
            logging.info("Received a message sender: " + sender)
            logging.info("Received a message from_email: " + from_email)
            logging.info("Received a message from_name: " + from_name)
            logging.info("Received a message subject: " + subject)
            logging.info("Received a message to email: " + email)
            logging.info("Received a message html: " + html)
            logging.info("Received a message text: " + text)

            #Identify and request any identified activation links
            register = RegisterMe()
            registered = "Registered: {}".format(register.activate(from_email, from_name, email, subject, text, html))

            logging.info(registered)
            logging.info(jsonobject)

            self.response.write(registered + '\n')
        self.response.write("Message Received")


app = webapp2.WSGIApplication([
                                (LogSenderHandler.mapping()),
                                ('/mandrill/?', Mandrill),
                                ('/.*', MainHandler)
                              ], debug=True)
