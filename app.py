from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from urllib.parse import urlparse, urljoin
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET', 'dev_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///voting.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# One-time DB initialization flag
_db_initialized = False


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Election(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    active = db.Column(db.Boolean, default=True)
    candidates = db.relationship('Candidate', backref='election', cascade='all, delete-orphan')


class Candidate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    election_id = db.Column(db.Integer, db.ForeignKey('election.id'), nullable=False)
    votes = db.Column(db.Integer, default=0)


class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    election_id = db.Column(db.Integer, db.ForeignKey('election.id'))


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def ensure_default_admin():
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(username='admin', is_admin=True)
        admin.set_password('admin')
        db.session.add(admin)
        db.session.commit()


@app.before_request
def init_db_once():
    global _db_initialized
    if _db_initialized:
        return
    with app.app_context():
        db.create_all()
        ensure_default_admin()
        # create a demo election so the UI shows example cards when DB is empty
        try:
            if Election.query.count() == 0:
                demo = Election(title='Demo Election', description='This is a demo election to show the UI.', active=True)
                db.session.add(demo)
                db.session.flush()
                db.session.add(Candidate(name='Alice', election_id=demo.id))
                db.session.add(Candidate(name='Bob', election_id=demo.id))
                db.session.commit()
        except Exception:
            db.session.rollback()
    _db_initialized = True


def is_safe_url(target):
    # prevent open redirects
    host_url = urlparse(request.host_url)
    redirect_url = urlparse(urljoin(request.host_url, target))
    return redirect_url.scheme in ('http', 'https') and host_url.netloc == redirect_url.netloc


@app.route('/')
def index():
    elections = Election.query.order_by(Election.id.desc()).all()
    return render_template('index.html', elections=elections)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        next_url = request.args.get('next') or request.form.get('next')
        if not username or not password:
            app.logger.info('Register attempt with missing fields: %s', request.remote_addr)
            flash('Username and password are required', 'warning')
            return redirect(url_for('register'))
        if len(password) < 6:
            app.logger.info('Register attempt with short password: %s', username)
            flash('Password must be at least 6 characters', 'warning')
            return redirect(url_for('register'))
        if User.query.filter_by(username=username).first():
            app.logger.info('Register attempt with existing username: %s', username)
            flash('Username already exists', 'danger')
            return redirect(url_for('register'))
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        app.logger.info('New user registered: %s', username)
        flash('Registration successful. You are now logged in.', 'success')
        if next_url and is_safe_url(next_url):
            return redirect(next_url)
        return redirect(url_for('index'))
    next_url = request.args.get('next')
    return render_template('register.html', next=next_url)


@app.route('/login', methods=['GET', 'POST'])
def login():
    next_url = request.args.get('next') or request.form.get('next')
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            app.logger.info('User logged in: %s', username)
            flash('Logged in successfully', 'success')
            if next_url and is_safe_url(next_url):
                return redirect(next_url)
            return redirect(url_for('index'))
        app.logger.info('Failed login for: %s from %s', username, request.remote_addr)
        flash('Invalid username or password', 'danger')
    return render_template('login.html', next=next_url)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out', 'info')
    return redirect(url_for('index'))


@app.route('/admin/create', methods=['GET', 'POST'])
@login_required
def create_election():
    if not current_user.is_admin:
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))
    if request.method == 'POST':
        title = request.form['title'].strip()
        description = request.form.get('description', '').strip()
        candidates_raw = request.form.get('candidates', '').strip()
        if not title or not candidates_raw:
            flash('Title and at least one candidate required', 'warning')
            return redirect(url_for('create_election'))
        election = Election(title=title, description=description)
        db.session.add(election)
        db.session.flush()
        for name in [c.strip() for c in candidates_raw.split(',') if c.strip()]:
            db.session.add(Candidate(name=name, election_id=election.id))
        db.session.commit()
        flash('Election created', 'success')
        return redirect(url_for('index'))
    return render_template('create_election.html')


@app.route('/election/<int:election_id>')
@login_required
def view_election(election_id):
    election = Election.query.get_or_404(election_id)
    voted = Vote.query.filter_by(user_id=current_user.id, election_id=election.id).first() is not None
    return render_template('vote.html', election=election, voted=voted)


@app.route('/election/<int:election_id>/vote', methods=['POST'])
@login_required
def cast_vote(election_id):
    election = Election.query.get_or_404(election_id)
    if Vote.query.filter_by(user_id=current_user.id, election_id=election.id).first():
        flash('You have already voted in this election', 'warning')
        return redirect(url_for('view_election', election_id=election.id))
    candidate_id = request.form.get('candidate')
    try:
        candidate_id = int(candidate_id)
    except (TypeError, ValueError):
        flash('Invalid candidate selected', 'danger')
        return redirect(url_for('view_election', election_id=election.id))
    candidate = Candidate.query.filter_by(id=candidate_id, election_id=election.id).first()
    if not candidate:
        flash('Invalid candidate selected', 'danger')
        return redirect(url_for('view_election', election_id=election.id))
    candidate.votes += 1
    db.session.add(Vote(user_id=current_user.id, election_id=election.id))
    db.session.commit()
    flash('Your vote has been recorded', 'success')
    return redirect(url_for('results', election_id=election.id))


@app.route('/api/election/<int:election_id>/vote', methods=['POST'])
@login_required
def api_cast_vote(election_id):
    election = Election.query.get_or_404(election_id)
    if Vote.query.filter_by(user_id=current_user.id, election_id=election.id).first():
        return jsonify({'status': 'error', 'message': 'You have already voted in this election'}), 400
    data = request.get_json(silent=True) or {}
    candidate_id = data.get('candidate_id')
    try:
        candidate_id = int(candidate_id)
    except (TypeError, ValueError):
        return jsonify({'status': 'error', 'message': 'Invalid candidate selected'}), 400
    candidate = Candidate.query.filter_by(id=candidate_id, election_id=election.id).first()
    if not candidate:
        return jsonify({'status': 'error', 'message': 'Invalid candidate selected'}), 400
    candidate.votes += 1
    db.session.add(Vote(user_id=current_user.id, election_id=election.id))
    db.session.commit()
    return jsonify({'status': 'ok', 'redirect': url_for('results', election_id=election.id)})


@app.route('/election/<int:election_id>/results')
@login_required
def results(election_id):
    election = Election.query.get_or_404(election_id)
    candidates = Candidate.query.filter_by(election_id=election.id).order_by(Candidate.votes.desc()).all()
    return render_template('results.html', election=election, candidates=candidates)


@app.errorhandler(401)
def unauthorized(e):
    # Login required or session expired
    flash('Please log in to continue', 'warning')
    return redirect(url_for('login'))


@app.errorhandler(403)
def forbidden(e):
    return render_template('403.html', message=str(e)), 403


@app.errorhandler(404)
def not_found(e):
    return render_template('404.html', message=str(e)), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return render_template('405.html', message=str(e)), 405


if __name__ == '__main__':
    app.run(debug=True)