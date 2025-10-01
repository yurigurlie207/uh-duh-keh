# Frontend Room Selection Example

## How Users Explicitly Choose Their Room

### 1. **Connection Flow**
```typescript
// In useSocket.ts
const connectToSocket = () => {
  const newSocket = io(SOCKET_URL, {
    auth: {
      token: token  // JWT contains household_id
    },
    transports: ["websocket"]
  });

  // User is connected but NOT in any room yet
  newSocket.on('connect', () => {
    console.log('✅ Connected to server');
    // User must now explicitly join a room
  });
};
```

### 2. **Room Selection UI**
```typescript
// In a React component
const [isInRoom, setIsInRoom] = useState(false);
const [currentRoom, setCurrentRoom] = useState(null);

const joinHouseholdRoom = () => {
  if (socket) {
    // Get household_id from JWT token or user context
    const householdId = getHouseholdIdFromToken(token);
    
    socket.emit('join_household', { 
      household_id: householdId 
    });
  }
};

// Listen for room join confirmation
useEffect(() => {
  if (socket) {
    socket.on('room_joined', (data) => {
      console.log('🏠 Joined room:', data.room);
      setIsInRoom(true);
      setCurrentRoom(data.room);
    });
    
    socket.on('error', (error) => {
      console.error('❌ Room error:', error.message);
      if (error.message.includes('household room first')) {
        // Show UI to join room
      }
    });
  }
}, [socket]);
```

### 3. **Room Selection Component**
```jsx
const RoomSelection = ({ onRoomJoined }) => {
  const [householdId, setHouseholdId] = useState('');
  
  const handleJoinRoom = () => {
    if (socket && householdId) {
      socket.emit('join_household', { household_id: householdId });
    }
  };
  
  return (
    <div className="room-selection">
      <h2>Choose Your Household</h2>
      <input 
        type="text" 
        value={householdId}
        onChange={(e) => setHouseholdId(e.target.value)}
        placeholder="Enter household ID"
      />
      <button onClick={handleJoinRoom}>
        Join Household Room
      </button>
    </div>
  );
};
```

### 4. **Main App Flow**
```jsx
const App = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [isInRoom, setIsInRoom] = useState(false);
  
  return (
    <div>
      {!isConnected && <LoginForm />}
      {isConnected && !isInRoom && <RoomSelection />}
      {isConnected && isInRoom && <TodosApp />}
    </div>
  );
};
```

### 5. **Error Handling**
```typescript
// Handle room-related errors
socket.on('error', (error) => {
  if (error.message.includes('household room first')) {
    // Show room selection UI
    setShowRoomSelection(true);
  } else if (error.message.includes('own household room')) {
    // Show error - user tried to join wrong household
    alert('You can only join your own household room');
  }
});
```

## **Key Benefits of Explicit Room Selection:**

### ✅ **User Control**
- Users explicitly choose when to join a room
- Clear separation between connection and room membership
- Users can see their room status

### ✅ **Security**
- Users can only join their own household room
- Room membership is validated on the server
- Clear error messages for unauthorized access

### ✅ **Flexibility**
- Users can connect without immediately joining a room
- Room membership is explicit and visible
- Easy to implement room switching (if needed later)

### ✅ **Better UX**
- Clear feedback about room status
- Users understand they need to join a room
- Room selection is a deliberate action

## **Server-Side Flow:**

1. **User connects** → Authenticated but not in any room
2. **User emits `join_household`** → Server validates and adds to room
3. **User can now perform todo operations** → All operations require room membership
4. **User disconnects** → Automatically leaves room

This approach gives users explicit control over their room membership while maintaining security and providing clear feedback about their connection status.


