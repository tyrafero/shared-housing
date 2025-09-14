# SharedHousing Platform

A comprehensive Django-based platform that connects people seeking shared accommodation in Australian cities, featuring smart roommate matching, property search integration, and group coordination tools.

## 🏠 Overview

SharedHousing addresses housing affordability through intelligent roommate matching, secure communication, and coordinated property applications, specifically targeting students, young professionals, and recent migrants in Sydney and Darwin.

## ✨ Key Features

- **Smart Roommate Matching**: Compatibility algorithm based on lifestyle, budget, and preferences
- **Integrated Property Search**: Browse properties from multiple real estate sites
- **Secure Group Formation**: Create and manage roommate groups with voting and coordination tools
- **Real-time Messaging**: WebSocket-powered instant communication
- **Coordinated Applications**: Apply for properties as a group
- **User Verification**: Multi-step verification process for safety
- **Mobile-First Design**: Responsive Bootstrap 5 interface

## 🛠 Technology Stack

- **Backend**: Django 4.2+, Python 3.12
- **Database**: PostgreSQL (SQLite for development)
- **Frontend**: Bootstrap 5, JavaScript
- **Real-time**: Django Channels with Redis
- **Task Queue**: Celery with Redis
- **Authentication**: Custom User model with email-based auth
- **Email**: SMTP integration with HTML templates
- **Forms**: Django Crispy Forms with Bootstrap 5

## 📁 Project Structure

```
shared_housing/
├── accounts/          # User authentication and management
├── profiles/          # User profiles and preferences
├── matching/          # Compatibility algorithm and matching
├── properties/        # Property listings and search
├── messaging/         # Real-time communication system
├── groups/            # Roommate group management
├── applications/      # Property application workflow
├── core/              # Shared utilities and base views
├── templates/         # Django templates
├── static/            # Static files (CSS, JS, images)
├── media/             # User uploaded files
└── shared_housing/    # Main Django project
    ├── settings/      # Environment-specific settings
    │   ├── base.py
    │   ├── development.py
    │   └── production.py
    └── ...
```

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- Virtual environment (recommended)

### Installation

1. **Clone and setup**:
```bash
cd shared-housing
python -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate
pip install -r requirements.txt
```

2. **Environment Configuration**:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. **Database Setup**:
```bash
python manage.py migrate
python manage.py collectstatic
```

4. **Create Superuser**:
```bash
python manage.py createsuperuser
```

5. **Run Development Server**:
```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000` to see the application.

## 🔧 Development Setup

### Environment Variables (.env)
```env
DEBUG=True
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///db.sqlite3
REDIS_URL=redis://localhost:6379/0
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
EMAIL_USE_TLS=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

### Settings Structure
- `base.py`: Common settings for all environments
- `development.py`: Development-specific settings (SQLite, debug toolbar)
- `production.py`: Production settings (PostgreSQL, security headers)

## 📱 Features Implemented

### ✅ Completed
1. **Project Foundation**
   - Django 4.2 project with modular app structure
   - Environment-specific settings (base/development/production)
   - Static files and media handling
   - Bootstrap 5 responsive design

2. **User Authentication System**
   - Custom User model with email authentication
   - Registration with email verification
   - Login/logout with password reset
   - Email verification tokens and templates
   - Admin interface for user management

3. **Multi-Step Profile System**
   - Comprehensive UserProfile model with 40+ fields
   - 6-step profile setup wizard:
     - Personal Information (age, occupation, education)
     - Location Preferences (suburbs, commute, transport)
     - Budget & Housing (rent range, room type, move-in date)
     - Lifestyle & Habits (cleanliness, social level, pets, smoking)
     - Roommate Preferences (age range, gender, max roommates)
     - About Yourself (bio, interests, languages, photos)
   - Profile completion tracking and progress indicators
   - Profile viewing and editing system
   - Smart step navigation with skip options

4. **Frontend Foundation**
   - Responsive navigation with user profiles
   - Professional landing page with feature showcase
   - Interactive dashboard with profile completion tracking
   - Multi-step form wizard with progress bars
   - Profile display with compatibility indicators
   - Form styling with Crispy Forms and custom CSS

### 📋 Ready for Implementation
- Property models and search integration
- Smart compatibility matching algorithm
- Real-time messaging with WebSockets
- Group formation and management tools
- Property application workflow
- Advanced search and filtering

## 🎨 Design System

### Colors
- Primary: `#0d6efd` (Bootstrap Blue)
- Success: `#198754` (Bootstrap Green)
- Warning: `#ffc107` (Bootstrap Yellow)
- Danger: `#dc3545` (Bootstrap Red)

### Components
- Cards with hover effects and shadows
- Form controls with focus states
- Compatibility scoring visual indicators
- Activity feed with timeline design
- Mobile-first responsive navigation

## 🔐 Security Features

- Email-based authentication (no username)
- Email verification required
- Terms of Service and Privacy Policy acceptance
- CSRF protection
- Secure session handling
- Content security headers (in production)
- Rate limiting preparation

## 🧪 Testing

Run the Django development server:
```bash
python manage.py runserver
```

Test the authentication flow:
1. Visit home page at `http://127.0.0.1:8000`
2. Register a new account
3. Check console for verification email
4. Login with created account
5. Access dashboard

## 📈 Next Steps

1. **Profile System**: Multi-step profile creation with preferences
2. **Property Integration**: Models for properties and search functionality
3. **Matching Algorithm**: Compatibility scoring and recommendations
4. **Real-time Features**: WebSocket integration for instant messaging
5. **Group Coordination**: Roommate group management tools

## 🤝 Contributing

This is a foundational implementation for a shared housing platform. The architecture supports scaling with additional features and integrations.

## 📄 License

This project is built as a comprehensive example of a Django-based shared housing platform.

---

**Status**: Foundation Complete ✅ | Authentication System ✅ | Profile System Complete ✅ | Ready for Property & Matching Systems 🚀

## 🧪 Testing the System

### Quick Setup for Testing

1. **Create Test Data**:
```bash
python manage.py create_test_users --count 5
```
This creates 5 test users with completed profiles (password: `testpass123`)

2. **Start Development Server**:
```bash
python manage.py runserver
```

3. **Test the Complete Flow**:
   - **Home Page**: `http://127.0.0.1:8000` - Landing page with features
   - **Register**: Create new account or login with test users
   - **Profile Setup**: Complete the 6-step wizard (if new user)
   - **Dashboard**: View profile completion and activity
   - **Profile Views**: Browse and edit profiles
   - **Admin Panel**: `http://127.0.0.1:8000/admin/` - Manage users and profiles

### Test User Accounts
- **Emails**: `testuser1@example.com` through `testuser5@example.com`
- **Password**: `testpass123` (for all test accounts)
- **Features**: Completed profiles with realistic sample data

### Key Features to Test
- ✅ User registration with email verification
- ✅ 6-step profile setup with validation
- ✅ Profile completion tracking
- ✅ Profile viewing and editing
- ✅ Dashboard with user activity
- ✅ Responsive design on mobile/desktop

The TemplateSyntaxError has been resolved, and all profile functionality is working correctly.