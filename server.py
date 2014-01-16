import config
from models import User, Change

import datetime
from flask import Flask, render_template

app = Flask(__name__)
app.config.from_object(config.FlaskConfig)


@app.template_filter()
def timeago(datetime_object, timeago=True):
    readable = datetime_object.strftime('%Y-%m-%d @ %H:%M')
    if not timeago:
        return readable
    iso_format = datetime_object.strftime('%Y-%m-%dT%H:%M:%SZ')
    return '<span class=timeago title="%s">%s</span>' % (iso_format, readable)


def pct_from_ints(smaller, larger):
    return int(round(float(smaller) / larger * 100))


def calc_score(chars_add, chars_del, new_pages):
    scoring = config.ScoringConfig
    return (chars_add * scoring.char_add_points +
            chars_del * scoring.char_del_points +
            new_pages * scoring.new_page_points)


def all_users_edit_chars_pcts(period=datetime.timedelta(days=7)):
    """
    Get the following for all users:

    * added and deleted characters for all users' edits
    * scaled bar percent values for each user's characters added/deleted
    * the number of new pages created by each user
    * the number of points (the score) each user has, based on the scoring
      constants in config.ScoringConfig
    * scaled bar percent values for each user's score

    Return the results in a list with the following format:
    [{'username': 'PhilipJFry',
      'pos_chars': 42,
      'pos_chars_pct': 27,
      'neg_chars': 100,
      'neg_chars_pct': 94,
      'new_pages': 0,
      'score': 3000,
      'score_pct': 12},
      {...}, ...]
    """
    earliest_dt = datetime.datetime.now() - period
    users = []
    chars_max = 0
    score_max = 0
    for user in User.select():
        username = user.username
        pos_chars = 0
        neg_chars = 0
        new_pages = 0
        for change in user.changes.where(Change.timestamp > earliest_dt):
            diff = change.size_diff
            if diff >= 0:
                pos_chars += diff
            else:
                neg_chars -= diff
            if change.change_type == 'new':
                new_pages += 1
        score = calc_score(pos_chars, neg_chars, new_pages)
        users.append({'username': username,
                      'pos_chars': pos_chars,
                      'neg_chars': neg_chars,
                      'new_pages': new_pages,
                      'score': score})
        if pos_chars > chars_max:
            chars_max = pos_chars
        if neg_chars > chars_max:
            chars_max = neg_chars
        if score > score_max:
            score_max = score
    min_char_bar_dec = float(config.LayoutConfig.min_char_bar_pct) / 100
    min_score_bar_dec = float(config.LayoutConfig.min_score_bar_pct) / 100
    pos_chars_add = chars_max * min_char_bar_dec
    neg_chars_add = chars_max * min_char_bar_dec
    score_add = score_max * min_score_bar_dec
    for user_data in users:

        # Positive bar minimum sizing
        if user_data['pos_chars'] == chars_max:
            user_data['pos_chars_pct'] = 100
        else:
            pos_pct = pct_from_ints(user_data['pos_chars'] + pos_chars_add,
                                    chars_max + pos_chars_add)
            user_data['pos_chars_pct'] = pos_pct

        # Negative bar minimum sizing
        if user_data['neg_chars'] == chars_max:
            user_data['neg_chars_pct'] = 100
        else:
            neg_pct = pct_from_ints(user_data['neg_chars'] + neg_chars_add,
                                    chars_max + neg_chars_add)
            user_data['neg_chars_pct'] = neg_pct

        # Score bar minimum sizing
        if user_data['score'] == score_max:
            user_data['score_pct'] = 100
        else:
            score_pct = pct_from_ints(user_data['score'] + score_add,
                                      score_max + score_add)
            user_data['score_pct'] = score_pct

    # Sort the list by most points and return it.
    users.sort(key=lambda u: u['score'], reverse=True)
    return users


def get_recent_changes(num_changes=
                       config.LayoutConfig.num_recent_changes):
    changes = (Change.select()
               .order_by(Change.timestamp.desc())
               .limit(num_changes))
    return changes


def get_change_score(change):
    chars_add = 0
    chars_del = 0
    new_page = 0
    if change.size_diff > 0:
        chars_add = change.size_diff
    else:
        chars_del = abs(change.size_diff)
    if change.change_type == 'new':
        new_page = 1
    return calc_score(chars_add, chars_del, new_page)


def get_multiple_change_scores(changes):
    return {c.id: get_change_score(c) for c in changes}


@app.route('/')
def index():
    recent_changes = get_recent_changes()
    change_scores = get_multiple_change_scores(recent_changes)
    return render_template('index.html',
                           users=all_users_edit_chars_pcts(),
                           scoring_config=config.ScoringConfig,
                           recent_changes=recent_changes,
                           change_scores=change_scores)

if __name__ == '__main__':
    app.run()
