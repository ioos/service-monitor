from flask import render_template, make_response, request
from ioos_catalog import app

@app.route('/help', methods=['GET'])
def help():
    return render_template('help.html')

@app.route('/help/feedback', methods=['GET'])
def feedback():
    return render_template('feedback.html')

@app.route('/help/feedback/submit', methods=['POST'])
def feedback_post():

    name = request.form['name']
    email = request.form['email']
    comments = request.form['comments']
    captcha_text = request.form['captcha_text']
    app.logger.info("Name: %s", name)
    app.logger.info("Email: %s", email)
    app.logger.info("Comments: %s", comments)
    app.logger.info("Captcha Text: %s", captcha_text)
    #app.logger.info("Captcha Image: %s", captcha_img)
    return make_response("", 200)

