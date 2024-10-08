from flask_bcrypt import Bcrypt
from flask_sqlalchemy import SQLAlchemy

bcrypt = Bcrypt()
db = SQLAlchemy()

class Follows(db.Model):
    """Connection of a follower <-> followed_user."""

    __tablename__ = 'follows'

    user_being_followed_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete="cascade"),
        primary_key=True,
    )

    user_following_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete="cascade"),
        primary_key=True,
    )


class User(db.Model):
    """User in the system."""

    __tablename__ = 'users'

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    email = db.Column(
        db.Text,
        nullable=False,
        unique=True,
    )

    username = db.Column(
        db.Text,
        nullable=False,
        unique=True,
    )

    first_name = db.Column(
        db.Text,
        nullable=False
    )
    
    last_name = db.Column(
        db.Text,
        nullable=False
    )

    image_url = db.Column(
        db.Text,
        default="/static/images/default-pic.png",
    )

    header_image_url = db.Column(
        db.Text,
        default="/static/images/warbler-hero.jpg"
    )

    sneaker_size = db.Column(
        db.Text,
        nullable=True,
    )

    password = db.Column(
        db.Text,
        nullable=False,
    )

    """Relationships"""

    sneakers_in_closet = db.relationship(
        'Closet',
        back_populates='user',
        lazy=True
    )

    sneakers_in_wishlist = db.relationship(
        'Wishlist',
        back_populates='user',
        lazy=True
    )

    followers = db.relationship(
        "User",
        secondary="follows",
        primaryjoin=(Follows.user_being_followed_id == id),
        secondaryjoin=(Follows.user_following_id == id),
        overlaps="following"
    )

    following = db.relationship(
        "User",
        secondary="follows",
        primaryjoin=(Follows.user_following_id == id),
        secondaryjoin=(Follows.user_being_followed_id == id),
        overlaps="followers"
    )

    def __repr__(self):
        return f"<User #{self.id}: {self.username}, {self.email}>"

    def is_followed_by(self, other_user):
        """Is this user followed by `other_user`?"""

        found_user_list = [user for user in self.followers if user == other_user]
        return len(found_user_list) == 1

    def is_following(self, other_user):
        """Is this user following `other_use`?"""

        found_user_list = [user for user in self.following if user == other_user]
        return len(found_user_list) == 1



    @classmethod
    def signup(cls, username, first_name, last_name, email, password, image_url):
        """Sign up user.

        Hashes password and adds user to system.
        """

        hashed_pwd = bcrypt.generate_password_hash(password).decode('UTF-8')

        user = User(
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=hashed_pwd,
            image_url=image_url,
        )

        db.session.add(user)
        # db.session.commit()
        return user
    

    @classmethod
    def authenticate(cls, username, password):
        """Find user with `username` and `password`.

        This is a class method (call it on the class, not an individual user.)
        It searches for a user whose password hash matches this password
        and, if it finds such a user, returns that user object.

        If can't find matching user (or if password is wrong), returns False.
        """

        user = cls.query.filter_by(username=username).first()

        if user:
            is_auth = bcrypt.check_password_hash(user.password, password)
            if is_auth:
                return user

        return False
    
    
    @property
    def full_name(self):
        """Return full name of user."""

        return f"{self.first_name} {self.last_name}"
    

class Sneaker(db.Model):

    __tablename__ = 'sneakers'

    id = db.Column(db.Integer, primary_key=True)
    sneaker_name = db.Column(db.String(120), nullable=False)
    brand = db.Column(db.String(50), nullable=False)
    sneaker_image = db.Column(db.Text, default="/static/images/default-pic.png",)
    retail_price = db.Column(db.Float)
    url = db.Column(db.Text)

    # Other sneaker-specific details can be added as needed


class Closet(db.Model):
    """Sneaker Closet associated with a user."""

    __tablename__ = 'closet'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    sneaker_id = db.Column(db.Integer, db.ForeignKey('sneakers.id'), nullable=False)

    user = db.relationship('User', back_populates='sneakers_in_closet')
    sneaker = db.relationship('Sneaker', lazy=True)
    

class Wishlist(db.Model):
    """Sneaker Wishlist associated with a user."""

    __tablename__ = 'wishlist'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    sneaker_id = db.Column(db.Integer, db.ForeignKey('sneakers.id'), nullable=False)

    user = db.relationship('User', back_populates='sneakers_in_wishlist')
    sneaker = db.relationship('Sneaker', lazy=True)


def connect_db(app):
    """Connect this database to provided Flask app.

    You should call this in your Flask app.
    """

    db.app = app
    db.init_app(app)



