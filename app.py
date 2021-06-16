import re
import traceback
from flask import Flask, render_template, url_for, request, redirect
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime
from flask_admin import Admin, AdminIndexView
from flask_admin.contrib.sqla import ModelView
from flask_security import UserMixin, RoleMixin, SQLAlchemyUserDatastore, Security, login_required, current_user
import email_validator


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///base.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = '1q2w3e4r5t'
app.config['SECURITY_PASSWORD_SALT'] = 'salt'
app.config['SECURITY_PASSWORD_HASH'] = 'sha512_crypt'
db = SQLAlchemy(app)
migrate = Migrate(app, db)


def slugify(s):
    pattern = r'[^\w+]'
    return re.sub(pattern, '-', s)


post_tags = db.Table('post_tags',
                     db.Column('post_id', db.Integer, db.ForeignKey('post.id')),
                     db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'))
                     )


roles_users = db.Table('roles_users',
                       db.Column('user_id', db.Integer(), db.ForeignKey('user.id')),
                       db.Column('role_id', db.Integer(), db.ForeignKey('role.id')))


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(255))
    active = db.Column(db.Boolean())
    roles = db.relationship('Role', secondary=roles_users, backref=db.backref('users', lazy='dynamic'))


class Role(db.Model, RoleMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True)
    description = db.Column(db.String(255))


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    intro = db.Column(db.String(300), nullable=False)
    body = db.Column(db.Text, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return '<Post %r>' % self.id

    tags = db.relationship('Tag', secondary=post_tags, backref=db.backref('posts', lazy='dynamic'))


class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), nullable=False)

    def __init__(self, *args, **kwargs):
        super(Tag, self).__init__(*args, **kwargs)
        self.slug = slugify(self.name)

    def __repr__(self):
        return '{}'.format(self.name)


@app.route('/')
def index():
    return render_template("index.html")


@app.route('/about')
def about():
    return render_template("about.html")


@app.route('/blog')
def blog():
    q = request.args.get('q')
    page = request.args.get('page')

    if page and page.isdigit():
        page = int(page)
    else:
        page = 1

    if q:
        posts = Post.query.order_by(Post.date.desc()).filter(Post.title.contains(q) | Post.body.contains(q)) #.all()
    else:
        posts = Post.query.order_by(Post.date.desc()) #.all()

    pages = posts.paginate(page=page, per_page=2)

    return render_template("blog.html", posts=posts, pages=pages)


@app.route('/posts/<int:id>')
def post_detail(id):
    post = Post.query.get_or_404(id)
    tags = post.tags
    return render_template("post_detail.html", post=post, tags=tags)


@app.route('/posts/<int:id>/delete')
@login_required
def post_delete(id):
    post = Post.query.get_or_404(id)

    try:
        db.session.delete(post)
        db.session.commit()
        return redirect('/blog')
    except:
        return traceback.format_exc()


@app.route('/posts/<int:id>/update', methods=['POST', 'GET'])
@login_required
def post_update(id):
    post = Post.query.get_or_404(id)
    if request.method == "POST":
        post.title = request.form['title']
        post.intro = request.form['intro']
        post.body = request.form['body']

        try:
            db.session.commit()
            return redirect('/blog')
        except:
            return traceback.format_exc()
    else:
        return render_template("post_update.html", post=post)


@app.route('/create_post', methods=['POST', 'GET'])
@login_required
def create_post():
    if request.method == "POST":
        title = request.form['title']
        intro = request.form['intro']
        body = request.form['body']

        post = Post(title=title, intro=intro, body=body)

        try:
            db.session.add(post)
            db.session.commit()
            return redirect('/blog')
        except:
            return traceback.format_exc()
    else:
        return render_template("create_post.html")


@app.route('/tag/<slug>')
def tag_detail(slug):
    tag = Tag.query.filter(Tag.slug == slug).first_or_404()
    posts = tag.posts.all()
    return render_template('tag_detail.html', tag=tag, posts=posts)


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


### ADMIN ###
class AdminMixin:
    def is_accessible(self):
        return current_user.has_role('admin')

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('security.login', next=request.url))


class AdminView(AdminMixin, ModelView):
    pass


class HomeAdminView(AdminMixin, AdminIndexView):
    pass


admin = Admin(app, 'FlaskApp', url='/', index_view=HomeAdminView(name='Home'))
admin.add_view(AdminView(Post, db.session))
admin.add_view(AdminView(Tag, db.session))


### Flask-security ###
user_datastore = SQLAlchemyUserDatastore(db, User, Role)
security = Security(app, user_datastore)


if __name__ == "__main__":
    app.run(debug=True)
