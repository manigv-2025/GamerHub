from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import json
from functools import wraps
from dotenv import load_dotenv
import re

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'gamerhub-dev-key-12345')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gamerhub.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db = SQLAlchemy(app)

# ==================== DATABASE MODELS ====================

class BlogPost(db.Model):
    """Blog post model"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), unique=True, nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    category = db.Column(db.String(50), nullable=False)  # Hardware Review, Gaming News, GTA V Mods
    author = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    content = db.Column(db.Text, nullable=False)
    featured_image = db.Column(db.String(500), default='https://via.placeholder.com/800x400?text=Gaming')
    rating = db.Column(db.Float, default=0)  # 1-10 for reviews
    pros = db.Column(db.Text, default='[]')  # JSON string
    cons = db.Column(db.Text, default='[]')  # JSON string
    affiliate_link = db.Column(db.String(500), default='')
    views = db.Column(db.Integer, default=0)
    published = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'slug': self.slug,
            'category': self.category,
            'author': self.author,
            'description': self.description,
            'content': self.content,
            'featured_image': self.featured_image,
            'rating': self.rating,
            'pros': json.loads(self.pros),
            'cons': json.loads(self.cons),
            'affiliate_link': self.affiliate_link,
            'views': self.views,
            'published': self.published,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class Admin(db.Model):
    """Admin user model"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# ==================== HELPER FUNCTIONS ====================

def generate_slug(title):
    """Generate URL-friendly slug from title"""
    slug = re.sub(r'[^\w\s-]', '', title.lower())
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug.strip('-')


def login_required_admin(f):
    """Decorator to check admin login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            flash('Please login first', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function


# ==================== PUBLIC ROUTES ====================

@app.route('/')
def index():
    """Homepage - show latest posts"""
    posts = BlogPost.query.filter_by(published=True).order_by(BlogPost.created_at.desc()).limit(6).all()
    return render_template('index.html', posts=posts)


@app.route('/reviews')
def reviews():
    """Hardware reviews page"""
    posts = BlogPost.query.filter_by(category='Hardware Review', published=True).order_by(BlogPost.created_at.desc()).all()
    return render_template('reviews.html', posts=posts, category='Hardware Reviews')


@app.route('/news')
def news():
    """Gaming news page"""
    posts = BlogPost.query.filter_by(category='Gaming News', published=True).order_by(BlogPost.created_at.desc()).all()
    return render_template('news.html', posts=posts, category='Gaming News')


@app.route('/mods')
def mods():
    """GTA V mods page"""
    posts = BlogPost.query.filter_by(category='GTA V Mods', published=True).order_by(BlogPost.created_at.desc()).all()
    return render_template('mods.html', posts=posts, category='GTA V Mods')


@app.route('/article/<slug>')
def article(slug):
    """View single article"""
    post = BlogPost.query.filter_by(slug=slug, published=True).first_or_404()
    post.views += 1
    db.session.commit()
    pros = json.loads(post.pros) if post.pros else []
    cons = json.loads(post.cons) if post.cons else []
    return render_template('article.html', post=post, pros=pros, cons=cons)


@app.route('/search')
def search():
    """Search functionality"""
    query = request.args.get('q', '').strip()
    results = []
    
    if query:
        results = BlogPost.query.filter(
            (BlogPost.title.ilike(f'%{query}%') | 
             BlogPost.description.ilike(f'%{query}%') |
             BlogPost.content.ilike(f'%{query}%')),
            BlogPost.published == True
        ).all()
    
    return render_template('search.html', query=query, results=results)


# ==================== ADMIN ROUTES ====================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        admin = Admin.query.filter_by(username=username).first()
        if admin and admin.check_password(password):
            session['admin_id'] = admin.id
            session['admin_username'] = admin.username
            flash('Login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('admin_login.html')


@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))


@app.route('/admin/dashboard')
@login_required_admin
def admin_dashboard():
    """Admin dashboard"""
    total_posts = BlogPost.query.count()
    published_posts = BlogPost.query.filter_by(published=True).count()
    total_views = db.session.query(db.func.sum(BlogPost.views)).scalar() or 0
    recent_posts = BlogPost.query.order_by(BlogPost.created_at.desc()).limit(5).all()
    
    return render_template('admin_dashboard.html',
                         total_posts=total_posts,
                         published_posts=published_posts,
                         total_views=total_views,
                         recent_posts=recent_posts)


@app.route('/admin/create', methods=['GET', 'POST'])
@login_required_admin
def admin_create():
    """Create new post"""
    if request.method == 'POST':
        title = request.form.get('title')
        category = request.form.get('category')
        author = request.form.get('author')
        description = request.form.get('description')
        content = request.form.get('content')
        featured_image = request.form.get('featured_image', 'https://via.placeholder.com/800x400?text=Gaming')
        rating = float(request.form.get('rating', 0))
        affiliate_link = request.form.get('affiliate_link', '')
        published = request.form.get('published') == 'on'
        
        # Parse pros and cons
        pros_text = request.form.get('pros', '')
        cons_text = request.form.get('cons', '')
        pros = [p.strip() for p in pros_text.split('\n') if p.strip()]
        cons = [c.strip() for c in cons_text.split('\n') if c.strip()]
        
        slug = generate_slug(title)
        
        # Check if slug already exists
        if BlogPost.query.filter_by(slug=slug).first():
            flash('A post with this title already exists', 'error')
            return redirect(url_for('admin_create'))
        
        post = BlogPost(
            title=title,
            slug=slug,
            category=category,
            author=author,
            description=description,
            content=content,
            featured_image=featured_image,
            rating=rating,
            pros=json.dumps(pros),
            cons=json.dumps(cons),
            affiliate_link=affiliate_link,
            published=published
        )
        
        db.session.add(post)
        db.session.commit()
        flash('Post created successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('admin_create.html', categories=['Hardware Review', 'Gaming News', 'GTA V Mods'])


@app.route('/admin/edit/<int:post_id>', methods=['GET', 'POST'])
@login_required_admin
def admin_edit(post_id):
    """Edit existing post"""
    post = BlogPost.query.get_or_404(post_id)
    
    if request.method == 'POST':
        post.title = request.form.get('title')
        post.category = request.form.get('category')
        post.author = request.form.get('author')
        post.description = request.form.get('description')
        post.content = request.form.get('content')
        post.featured_image = request.form.get('featured_image', post.featured_image)
        post.rating = float(request.form.get('rating', post.rating))
        post.affiliate_link = request.form.get('affiliate_link', '')
        post.published = request.form.get('published') == 'on'
        
        # Parse pros and cons
        pros_text = request.form.get('pros', '')
        cons_text = request.form.get('cons', '')
        pros = [p.strip() for p in pros_text.split('\n') if p.strip()]
        cons = [c.strip() for c in cons_text.split('\n') if c.strip()]
        
        post.pros = json.dumps(pros)
        post.cons = json.dumps(cons)
        post.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash('Post updated successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    
    pros = json.loads(post.pros) if post.pros else []
    cons = json.loads(post.cons) if post.cons else []
    
    return render_template('admin_edit.html',
                         post=post,
                         pros='\n'.join(pros),
                         cons='\n'.join(cons),
                         categories=['Hardware Review', 'Gaming News', 'GTA V Mods'])


@app.route('/admin/delete/<int:post_id>')
@login_required_admin
def admin_delete(post_id):
    """Delete post"""
    post = BlogPost.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    flash('Post deleted successfully!', 'success')
    return redirect(url_for('admin_dashboard'))


# ==================== API ROUTES ====================

@app.route('/api/posts')
def api_posts():
    """Get all published posts as JSON"""
    category = request.args.get('category')
    limit = request.args.get('limit', 10, type=int)
    
    query = BlogPost.query.filter_by(published=True)
    
    if category:
        query = query.filter_by(category=category)
    
    posts = query.order_by(BlogPost.created_at.desc()).limit(limit).all()
    return jsonify([post.to_dict() for post in posts])


@app.route('/api/post/<slug>')
def api_post(slug):
    """Get single post as JSON"""
    post = BlogPost.query.filter_by(slug=slug, published=True).first_or_404()
    return jsonify(post.to_dict())


@app.route('/api/categories')
def api_categories():
    """Get all categories"""
    categories = db.session.query(BlogPost.category).distinct().filter_by(published=True).all()
    return jsonify([cat[0] for cat in categories])


# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(error):
    return render_template('500.html'), 500


# ==================== CREATE DATABASE ====================

with app.app_context():
    db.create_all()
    
    # Create default admin if doesn't exist
    if Admin.query.count() == 0:
        admin = Admin(username='admin', email='admin@gamerhub.local')
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print("✓ Default admin created: username='admin', password='admin123'")


# ==================== RUN APP ====================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'True') == 'True'
    app.run(host='0.0.0.0', port=port, debug=debug)
