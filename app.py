import os

from flask import Flask, render_template, request, flash, redirect, session, g, abort
from flask_debugtoolbar import DebugToolbarExtension
from sqlalchemy.exc import IntegrityError

from forms import UserAddForm, UserEditForm, LoginForm
from models import db, connect_db, User, Sneaker, Closet, Wishlist, Follows, Notification
from datetime import datetime

CURR_USER_KEY = "curr_user"

app = Flask(__name__)

# Get DB_URI from environ variable (useful for production/testing) or,
# if not set there, use development local db.
app.config['SQLALCHEMY_DATABASE_URI'] = (
    os.environ.get('DATABASE_URL', 'postgresql:///sneaker-closet'))

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ECHO'] = False
app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = True
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', "it's a secret")
toolbar = DebugToolbarExtension(app)

connect_db(app)


##############################################################################
# User signup/login/logout


@app.before_request
def add_user_to_g():
    """If we're logged in, add curr user to Flask global."""

    if CURR_USER_KEY in session:
        g.user = User.query.get(session[CURR_USER_KEY])

    else:
        g.user = None


def do_login(user):
    """Log in user."""

    session[CURR_USER_KEY] = user.id


def do_logout():
    """Logout user."""

    if CURR_USER_KEY in session:
        del session[CURR_USER_KEY]


@app.route('/signup', methods=["GET", "POST"])
def signup():
    """Handle user signup.

    Create new user and add to DB. Redirect to home page.

    If form not valid, present form.

    If the there already is a user with that username: flash message
    and re-present form.
    """
    if CURR_USER_KEY in session:
        del session[CURR_USER_KEY]
    form = UserAddForm()

    if form.validate_on_submit():
        try:
            user = User.signup(
                username=form.username.data,
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                password=form.password.data,
                email=form.email.data,
                image_url=form.image_url.data or User.image_url.default.arg,
            )
            db.session.commit()

        except IntegrityError as e:
            db.session.rollback()  # Roll back to keep the session clean
            flash("Username or email already taken", 'danger')
            return render_template('users/signup.html', form=form)


        do_login(user)

        """CHANGE THIS WHEN YOU HAVE ("/") FIGURED OUT"""
        return redirect("/sneakers")

    else:
        return render_template('users/signup.html', form=form)
    

@app.route('/login', methods=["GET", "POST"])
def login():
    """Handle user login."""

    form = LoginForm()

    if form.validate_on_submit():
        user = User.authenticate(form.username.data,
                                 form.password.data)

        if user:
            do_login(user)
            flash(f"Hello, {user.username}!", "success")
            return redirect("/sneakers")

        flash("Invalid credentials.", 'danger')

    return render_template('users/login.html', form=form)


@app.route('/logout')
def logout():
    """Handle logout of user."""

    do_logout()

    flash("You have successfully logged out.", 'success')
    return redirect("/login")


##############################################################################
# General sneaker related routes:

@app.route('/sneakers')
def list_sneakers():
    """Page with listing of sneakers.

    Can take a 'q' param in querystring to search by that sneaker.
    """

    search = request.args.get('q')

    if not search:
        sneakers = Sneaker.query.all()
    else:
        sneakers = Sneaker.query.filter(Sneaker.sneaker_name.ilike(f"%{search}%")).all()

    return render_template('users/sneaker_index.html', sneakers=sneakers)


@app.route('/sneakers/<int:sneaker_id>')
def sneaker_show(sneaker_id):
    """Show sneaker info page."""

    sneaker = Sneaker.query.get_or_404(sneaker_id)
    # # snagging messages in order from the database;
    # # user.messages won't be in order by default
    # messages = (Message
    #             .query
    #             .filter(Message.sneaker_id == sneaker_id)
    #             .order_by(Message.timestamp.desc())
    #             .limit(100)
    #             .all())
    # likes = [message.id for message in user.likes]
    return render_template('users/sneakers/show.html', sneaker=sneaker)


@app.route('/users/<int:user_id>/rotation')
def current_rotation(user_id):
    """Show user's current rotation (top five favored sneakers)."""

    if not g.user or g.user.id != user_id:
        flash("Access unauthorized.", "danger")
        return redirect("/")
    
    user = User.query.get_or_404(user_id)
    # Fetch sneakers in rotation
    rotation_sneakers = Closet.query.filter_by(user_id=user.id, is_liked=True).all()
    return render_template('users/sneakers/rotation.html', user=user, sneakers=rotation_sneakers)


@app.route('/sneakers/<int:sneaker_id>/rotation', methods=['POST'])
def adding_sneaker_rotation(sneaker_id):
    """Add or remove sneaker from current rotation (top five liked sneakers)."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    sneaker_entry = Closet.query.filter_by(user_id=g.user.id, sneaker_id=sneaker_id).first()
    if not sneaker_entry:
        flash("Sneaker not found in your closet.", "danger")
        return redirect(f"/users/{g.user.id}/closet")

    # Toggle like status, ensuring max of 5 sneakers are liked
    if sneaker_entry.is_liked:
        sneaker_entry.is_liked = False
    else:
        liked_count = Closet.query.filter_by(user_id=g.user.id, is_liked=True).count()
        if liked_count >= 5:
            flash("You can only like up to 5 sneakers.", "warning")
        else:
            sneaker_entry.is_liked = True

    db.session.commit()

    # Query the current liked sneakers for this user
    liked_sneakers = Closet.query.filter_by(user_id=g.user.id, is_liked=True).all()

    # Pass liked sneakers to the rotation.html template
    return render_template('users/sneakers/rotation.html', user=g.user, sneakers=liked_sneakers)


@app.route('/users/<int:user_id>/rotation/remove/<int:sneaker_id>', methods=['POST'])
def remove_from_rotation(user_id, sneaker_id):
    """Remove sneaker from user's rotation without leaving the page."""
    
    if not g.user or g.user.id != user_id:
        flash("Access unauthorized.", "danger")
        return redirect("/")
    
    # Find the sneaker entry in the Closet and update its status
    sneaker_entry = Closet.query.filter_by(user_id=user_id, sneaker_id=sneaker_id).first()
    if sneaker_entry and sneaker_entry.is_liked:
        sneaker_entry.is_liked = False
        db.session.commit()
    
    # Retrieve updated rotation list to display
    rotation_sneakers = Closet.query.filter_by(user_id=user_id, is_liked=True).all()
    return render_template('users/sneakers/rotation.html', user=g.user, sneakers=rotation_sneakers)


@app.route('/users/<int:user_id>/closet')
def show_closet(user_id):
    """Show list of sneakers that the user owns."""
    if not g.user or g.user.id != user_id:
        flash("Access unauthorized.", "danger")
        return redirect("/")
    
    user = User.query.get_or_404(user_id) 

    # Get all Closet entries for this user and extract Sneaker objects
    closet_sneakers = [entry.sneaker for entry in user.sneakers_in_closet]
    
    return render_template('users/sneakers/closet.html', sneakers=closet_sneakers, user=user)

@app.route('/users/<int:user_id>/wishlist')
def show_wishlist(user_id):
    """Show list of sneakers on the user's wishlist."""
    if not g.user or g.user.id != user_id:
        flash("Access unauthorized.", "danger")
        return redirect("/")
    
    user = User.query.get_or_404(user_id) 

    # Get all Wishlist entries for this user and extract Sneaker objects
    wishlist_sneakers = [entry.sneaker for entry in user.sneakers_in_wishlist]
    
    return render_template('users/sneakers/wishlist.html', sneakers=wishlist_sneakers, user=user)


@app.route('/users/add_own/<int:closet_id>', methods=['POST'])
def add_to_closet(closet_id):
    """Add a sneaker to the user's closet if it's not already there, and remove it from the wishlist if present."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")
    
    # Check if the sneaker is already in the Closet
    closet_entry = Closet.query.filter_by(user_id=g.user.id, sneaker_id=closet_id).first()
    if closet_entry:
        flash("Sneaker is already in your closet.", "info")
        return redirect(f"/users/{g.user.id}/closet")
    
    # Fetch the sneaker and add it to the Closet
    added_sneaker = Sneaker.query.get_or_404(closet_id)
    new_closet_entry = Closet(user_id=g.user.id, sneaker_id=added_sneaker.id)
    
    # Remove the sneaker from the Wishlist if it exists there
    wishlist_entry = Wishlist.query.filter_by(user_id=g.user.id, sneaker_id=added_sneaker.id).first()
    if wishlist_entry:
        db.session.delete(wishlist_entry)
    
    # Add the sneaker to the Closet
    db.session.add(new_closet_entry)
    
    # Create a notification
    notification_message = f"{g.user.username} added {added_sneaker.sneaker_name} to Closet"
    notification = Notification(user_id=g.user.id, message=notification_message, timestamp=datetime.utcnow())
    db.session.add(notification)
    
    # Commit all changes to the database
    db.session.commit()
    
    flash("Sneaker added to closet!", "success")
    return redirect(f"/users/{g.user.id}/closet")



@app.route('/users/remove_own/<int:closet_id>', methods=['POST'])
def remove_from_closet(closet_id):
    """Remove sneaker from user's closet."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    closet_entry = Closet.query.filter_by(user_id=g.user.id, sneaker_id=closet_id).first()
    if closet_entry:
        db.session.delete(closet_entry)
        db.session.commit()

    return redirect(f"/users/{g.user.id}/closet")


@app.route('/users/add_wishlist/<int:wishlist_id>', methods=['POST'])
def add_to_wishlist(wishlist_id):
    """Add a sneaker to the user's wishlist if it's not already there."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")
    
    # Check if the sneaker is already in the Wishlist
    wishlist_entry = Wishlist.query.filter_by(user_id=g.user.id, sneaker_id=wishlist_id).first()
    if wishlist_entry:
        flash("Sneaker is already in your wishlist.", "info")
        return redirect(f"/users/{g.user.id}/wishlist")
    
    # Fetch the sneaker and add it to the Wishlist
    added_sneaker = Sneaker.query.get_or_404(wishlist_id)
    new_wishlist_entry = Wishlist(user_id=g.user.id, sneaker_id=added_sneaker.id)
    
    db.session.add(new_wishlist_entry)
    
    # Create a notification
    notification_message = f"{g.user.username} added {added_sneaker.sneaker_name} to Wishlist"
    notification = Notification(user_id=g.user.id, message=notification_message, timestamp=datetime.utcnow())
    db.session.add(notification)
    
    # Commit all changes to the database
    db.session.commit()
    
    flash("Sneaker added to wishlist!", "success")
    return redirect(f"/users/{g.user.id}/wishlist")


@app.route('/users/remove_wishlist/<int:wishlist_id>', methods=['POST'])
def remove_from_wishlist(wishlist_id):
    """Remove sneaker from user's wishlist."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    wishlist_entry = Wishlist.query.filter_by(user_id=g.user.id, sneaker_id=wishlist_id).first()
    if wishlist_entry:
        db.session.delete(wishlist_entry)
        db.session.commit()

    return redirect(f"/users/{g.user.id}/wishlist")


##############################################################################
# General User related routes:

@app.route('/users')
def list_users():
    """Page with listing of users.

    Can take a 'q' param in querystring to search by that username.
    """

    search = request.args.get('q')

    if not search:
        users = User.query.filter(User.id != g.user.id).all()
    else:
        users = User.query.filter(User.username.ilike(f"%{search}%"), User.id != g.user.id).all()

    return render_template('users/users_index.html', users=users)


@app.route('/users/<int:user_id>/following')
def show_following(user_id):
    """Show list of people this user is following."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = User.query.get_or_404(user_id)
    return render_template('users/social/following.html', user=user)


@app.route('/users/<int:user_id>/followers')
def users_followers(user_id):
    """Show list of followers of this user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = User.query.get_or_404(user_id)
    return render_template('users/social/followers.html', user=user)


@app.route('/users/follow/<int:follow_id>', methods=['POST'])
def add_follow(follow_id):
    """Add a follow for the currently-logged-in user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    followed_user = User.query.get_or_404(follow_id)
    g.user.following.append(followed_user)
    db.session.commit()

    return redirect(f"/users/{g.user.id}/following")


@app.route('/users/stop-following/<int:follow_id>', methods=['POST'])
def stop_following(follow_id):
    """Have currently-logged-in-user stop following this user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    followed_user = User.query.get(follow_id)
    g.user.following.remove(followed_user)
    db.session.commit()

    return redirect(f"/users/{g.user.id}/following")


@app.route('/users/<int:user_id>')
def users_show(user_id):
    """Show user profile."""

    user = User.query.get_or_404(user_id)
    
    return render_template('users/profile.html', user=user)

@app.route('/users/profile', methods=["GET", "POST"])
def edit_profile():
    """Update profile for current user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = g.user
    form = UserEditForm(obj=user)

    if form.validate_on_submit():
        if User.authenticate(user.username, form.password.data):
            user.username = form.username.data
            user.first_name = form.first_name.data
            user.last_name = form.last_name.data
            user.email = form.email.data
            user.image_url = form.image_url.data or "/static/images/default-pic.png"
            user.header_image_url = form.header_image_url.data or "/static/images/warbler-hero.jpg"
            user.sneaker_size = form.sneaker_size.data

            db.session.commit()
            flash("Profile updated successfully!", "success")
            return redirect(f"/users/{user.id}")

        flash("Wrong password, please try again.", 'danger')

    return render_template('users/edit.html', form=form, user_id=user.id)


@app.route('/users/delete', methods=["POST"])
def delete_user():
    """Delete user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    do_logout()

    db.session.delete(g.user)
    db.session.commit()

    return redirect("/signup")

@app.route('/notifications')
def notifications():
    """Page for sneaker and follow related notifications"""

    if g.user:
        notifications = Notification.query.filter_by(user_id=g.user.id).order_by(Notification.timestamp.desc()).all()
        return render_template('users/notifications.html', notifications=notifications)

    else:
        flash("You need to log in to view notifications.", "danger")
        return redirect("/login")



@app.route('/test-notifications')
def test_notifications():
    try:
        return render_template('users/notifications.html')
    except Exception as e:
        print(e)
        return "Error rendering template"


##############################################################################
# Homepage and error pages


@app.route('/')
def homepage():
    """Show homepage:

    - anon users: no messages
    - logged in: 100 most recent messages of followed_users
    """

    

    if g.user:
        following_ids = [f.id for f in g.user.following] + [g.user.id]

        return render_template('sneaker_index.html')

    else:
        return render_template('home-anon.html')


@app.errorhandler(404)
def page_not_found(e):
    """404 NOT FOUND page."""

    return render_template('404.html'), 404


##############################################################################
# Turn off all caching in Flask
#   (useful for dev; in production, this kind of stuff is typically
#   handled elsewhere)
#
# https://stackoverflow.com/questions/34066804/disabling-caching-in-flask

@app.after_request
def add_header(req):
    """Add non-caching headers on every request."""

    req.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    req.headers["Pragma"] = "no-cache"
    req.headers["Expires"] = "0"
    req.headers['Cache-Control'] = 'public, max-age=0'
    return req
