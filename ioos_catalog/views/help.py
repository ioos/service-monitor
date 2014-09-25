from functools import partial

from flask import render_template, make_response, request
from flask.ext.captcha.models import CaptchaStore

from ioos_catalog import app
from ioos_catalog.tasks.send_email import send

from flask_captcha.views import db
from sqlalchemy.exc import InvalidRequestError, DBAPIError
import json

@app.route('/help', methods=['GET'])
@app.route('/help/', methods=['GET'])
def help():
    return render_template('help.html')

@app.route('/help/download', methods=['GET'])
@app.route('/help/download/', methods=['GET'])
def help_download():
    return render_template('help_download.html')

@app.route('/help/feedback', methods=['GET'])
def feedback():
    return render_template('feedback.html')

@app.route('/help/feedback/submit', methods=['POST'])
def feedback_post():
    try:
        form = request.get_json()

        name = form['name']
        email = form['email']
        comments = form['comments']
        captcha_text = form['captcha_text']
        captcha_img = form['captcha_img']


        invalid_fields = []
        if not name or name == 'Your Name':
            invalid_fields.append("nameLabel")
        if not email:
            invalid_fields.append("emailLabel")
        if not comments:
            invalid_fields.append("commentLabel")

        if invalid_fields:
            response_dict = {
                'status' : 'Missing Fields',
                'fields' : invalid_fields
            }
            return make_response(json.dumps(response_dict), 400)

        if captcha_validate(captcha_img, captcha_text):
            prepare_email(name, email, comments)
            return make_response('{"status": "Sent"}', 200)
        else:
            return make_response('{"status":"Invalid Captcha", "fields":["captchaInput"]}', 400)
    except KeyError:
        app.logger.exception("Failed to parse POST data")
        return make_response("{}", 500)


def prepare_email(name, email, comments):
    email_address = app.config.get('MAIL_COMMENTS_TO')
    subject = 'IOOS Catalog Comments'
    text_body = render_template('feedback_email.txt', name=name, email=email, comments=comments)
    html_body = None
    
    app.logger.info("Sending email on behalf of %s <%s>", name, email)
    send(subject, email_address, None, text_body, html_body)

@app.route('/help/feedback/success', methods=['GET'])
def feedback_success():
    return render_template('feedback_success.html')

def captcha_validate(hashkey, response):
    response = response.strip().lower()

    @serializable_retry
    def critical_path():
        if not app.config.get('CAPTCHA_PREGEN', False):
            CaptchaStore.remove_expired()
        if not CaptchaStore.validate(hashkey, response):
            return False
        return True

    return critical_path()

def serializable_retry(func, max_num_retries=None):
    '''
    This decorator calls another function whose next commit will be serialized.
    This might triggers a rollback. In that case, we will retry with some
    increasing (5^n * random, where random goes from 0.5 to 1.5 and n starts
    with 1) timing between retries, and fail after a max number of retries.
    '''
    def wrap(max_num_retries, *args, **kwargs):
        if max_num_retries is None:
            max_num_retries = app.config.get(
                'MAX_NUM_SERIALIZED_RETRIES', 1)

        retries = 1
        initial_sleep_time = 5 # miliseconds

        #set_serializable()
        while True:
            try:
                ret = func(*args, **kwargs)
                break
            except (InvalidRequestError, DBAPIError) as e:
                db.session.rollback()
                if retries > max_num_retries:
                    unset_serializable()
                    db.session.commit()
                    raise

                retries += 1
                sleep_time = (initial_sleep_time**retries) * (random.random() + 0.5)
                time.sleep(sleep_time * 0.001) # specified in seconds
            except Exception as e:
                raise

        #unset_serializable()
        db.session.commit()
        return ret

    return partial(wrap, max_num_retries)
