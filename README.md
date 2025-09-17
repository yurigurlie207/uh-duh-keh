# Todo Management System - React + Python

A modern todo management application with AI-powered prioritization, built with React frontend and Python FastAPI backend.

## Features

- 🔐 **User Authentication** - Login/Register with JWT tokens
- 📝 **Todo Management** - Create, update, delete, and toggle todos
- 👥 **User Assignment** - Assign todos to different family members
- 🤖 **AI Prioritization** - Claude AI integration for smart task prioritization
- ⚡ **Real-time Updates** - WebSocket support for live collaboration
- 🎯 **User Preferences** - Personalized task preferences for better AI suggestions
- 📱 **Responsive Design** - Modern UI with Tailwind CSS

## Tech Stack

### Frontend (React)
- **React 18** with TypeScript
- **React Router** for navigation
- **Socket.IO Client** for real-time communication
- **Axios** for HTTP requests
- **Tailwind CSS** for styling

### Backend (Python)
- **FastAPI** for REST API
- **Socket.IO** for WebSocket support
- **Python-Jose** for JWT authentication
- **Passlib** for password hashing
- **HTTPX** for external API calls
- **Pydantic** for data validation

## Project Structure

```
websocket-react-python-crud/
├── frontend/                 # React frontend
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── services/        # API services
│   │   ├── hooks/          # Custom React hooks
│   │   └── types/          # TypeScript types
│   ├── package.json
│   └── tailwind.config.js
├── backend/                 # Python backend
│   ├── main.py             # FastAPI application
│   ├── auth.py             # Authentication service
│   ├── ai_handlers.py      # Claude AI integration
│   └── requirements.txt
├── common/                 # Shared types
│   └── events.py
└── README.md
```

## Setup Instructions

### Prerequisites

- **Node.js** (v16 or higher)
- **Python** (v3.8 or higher)
- **Claude API Key** (for AI features)

### Backend Setup

1. **Navigate to backend directory:**
   ```bash
   cd backend
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   ```bash
   cp env.example .env
   # Edit .env and add your Claude API key
   CLAUDE_API_KEY=your_claude_api_key_here
   SECRET_KEY=your-secret-key-change-in-production
   ```

5. **Start the backend server:**
   ```bash
   python main.py
   ```

   The backend will be available at `http://localhost:3001`

### Frontend Setup

1. **Navigate to frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Set up environment variables:**
   ```bash
   cp env.example .env
   # Edit .env if needed (defaults should work)
   REACT_APP_API_URL=http://localhost:3001/api
   REACT_APP_SOCKET_URL=http://localhost:3001
   ```

4. **Start the development server:**
   ```bash
   npm start
   ```

   The frontend will be available at `http://localhost:3000`

## Usage

### Default Users

The system comes with pre-configured test users:
- **Username:** `mom` | **Password:** `mom123`
- **Username:** `dad` | **Password:** `dad123`
- **Username:** `kid` | **Password:** `kid123`

### Features Guide

1. **Login/Register:** Create an account or use the default users
2. **Add Todos:** Create new tasks and assign them to family members
3. **AI Prioritization:** Click "Prioritize with AI" to get smart task ordering
4. **User Preferences:** Set your preferences in the Profile page for better AI suggestions
5. **Real-time Updates:** Changes are synchronized across all connected users
6. **Bulk Actions:** Mark all tasks complete/incomplete or remove completed tasks

### AI Prioritization

The AI system considers:
- **User Preferences** - Tasks matching your preferred categories get higher priority
- **Task Dependencies** - Tasks that need to be done before others
- **Family Impact** - Tasks affecting multiple people
- **Time Sensitivity** - Urgent or time-sensitive tasks
- **Energy Levels** - When tasks are typically performed

## API Endpoints

### Authentication
- `POST /api/auth/login` - User login
- `POST /api/auth/register` - User registration

### Todos
- `GET /api/todos` - Get all todos
- `GET /api/users` - Get available users
- `GET /api/user-preferences` - Get user preferences
- `POST /api/user-preferences` - Update user preferences

### AI
- `POST /api/ai/prioritize` - Prioritize todos with AI
- `POST /api/ai/insights` - Get AI insights

### WebSocket Events

#### Client to Server
- `todo:create` - Create new todo
- `todo:update` - Update existing todo
- `todo:toggle` - Toggle todo completion
- `todo:delete` - Delete todo
- `todo:set_all` - Mark all todos complete/incomplete
- `todo:remove_completed` - Remove completed todos

#### Server to Client
- `todo:created` - Todo created
- `todo:updated` - Todo updated
- `todo:deleted` - Todo deleted
- `connect` - Connected to server
- `disconnect` - Disconnected from server

## Development

### Backend Development
```bash
cd backend
python main.py  # Starts with auto-reload
```

### Frontend Development
```bash
cd frontend
npm start  # Starts with hot reload
```

### Building for Production

**Frontend:**
```bash
cd frontend
npm run build
```

**Backend:**
```bash
cd backend
pip install -r requirements.txt
python main.py
```

## Environment Variables

### Backend (.env)
```env
CLAUDE_API_KEY=your_claude_api_key_here
SECRET_KEY=your-secret-key-change-in-production
HOST=0.0.0.0
PORT=3001
```

### Frontend (.env)
```env
REACT_APP_API_URL=http://localhost:3001/api
REACT_APP_SOCKET_URL=http://localhost:3001
```

## Troubleshooting

### Common Issues

1. **CORS Errors:** Make sure the backend CORS settings include your frontend URL
2. **WebSocket Connection Failed:** Check that both servers are running and ports are correct
3. **AI Prioritization Not Working:** Verify your Claude API key is set correctly
4. **Authentication Issues:** Check that JWT tokens are being sent with requests

### Debug Mode

Enable debug logging by setting environment variables:
```bash
export DEBUG=1  # Backend
export REACT_APP_DEBUG=true  # Frontend
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review the console logs for errors
3. Ensure all dependencies are installed correctly
4. Verify environment variables are set

---

**Note:** This is a converted version of the original Angular + Node.js application, maintaining all the same functionality while using React and Python instead.
