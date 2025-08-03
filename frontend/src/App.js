// frontend/src/App.js

import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import './App.css';

const API_BASE_URL = 'http://localhost:5000/api';

function App() {
  // --- State Management ---
  const [documents, setDocuments] = useState([]);
  const [sessions, setSessions] = useState([]); // List of available sessions
  const [currentSessionId, setCurrentSessionId] = useState(null); // ID of the active session
  const [messages, setMessages] = useState([]); // Messages for the current session
  const [inputMessage, setInputMessage] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isCreatingSession, setIsCreatingSession] = useState(false); // For new chat button
  const [selectedDocumentIds, setSelectedDocumentIds] = useState([]); // <-- New state for document selection
  const fileInputRef = useRef(null);
  const messagesEndRef = useRef(null);

  // --- Auto-scroll to bottom of messages ---
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // --- Fetch data on component mount ---
  useEffect(() => {
    const initializeApp = async () => {
      try {
        // Load documents and the list of available chat sessions
        await Promise.all([fetchDocuments(), fetchSessions()]);
        // Optionally, load the most recent session automatically
        // if (sessions.length > 0) {
        //   await loadSession(sessions[0].session_id); // Load the first (newest) session
        // }
      } catch (error) {
        console.error("Error during initialization:", error);
      }
    };

    initializeApp();
  }, []); // Run only once on mount

  // --- API Calls ---
  const fetchDocuments = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/documents`);
      setDocuments(response.data);
      // Optional: Clear selection if documents change significantly
      // setSelectedDocumentIds([]); 
    } catch (error) {
      console.error('Error fetching documents:', error);
      // Optionally, show an error message to the user
    }
  };

  const fetchSessions = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/sessions`);
      setSessions(response.data);
      // If no current session is set and sessions exist, you could auto-select the latest one here
      // if (!currentSessionId && response.data.length > 0) {
      //   await loadSession(response.data[0].session_id);
      // }
    } catch (error) {
      console.error('Error fetching sessions:', error);
      // Optionally, show an error message to the user
    }
  };

  const createNewSession = async () => {
    setIsCreatingSession(true);
    try {
      const response = await axios.post(`${API_BASE_URL}/sessions`);
      const newSessionId = response.data.session_id;
      setCurrentSessionId(newSessionId);
      setMessages([]); // Clear messages for the new session in the UI
      // Clear document selection when starting a new session (optional)
      setSelectedDocumentIds([]);
      await fetchSessions(); // Refresh the session list in the sidebar
      console.log("New session created:", newSessionId);
    } catch (error) {
      console.error('Error creating new session:', error);
      alert('Failed to create new chat session.');
    } finally {
      setIsCreatingSession(false);
    }
  };

  const loadSession = async (sessionId) => {
    if (!sessionId) return;
    try {
      const response = await axios.get(`${API_BASE_URL}/sessions/${sessionId}`);
      setCurrentSessionId(sessionId);
      // Set messages from the loaded session data
      setMessages(response.data.session.messages || []);
      // Clear document selection when loading a session (optional)
      setSelectedDocumentIds([]);
      console.log("Loaded session:", sessionId);
    } catch (error) {
      console.error('Error loading session:', error);
      alert('Failed to load chat session.');
    }
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    if (!file.name.endsWith('.pdf')) {
      alert('Please upload a PDF file');
      return;
    }

    setIsUploading(true);
    const formData = new FormData();
    formData.append('pdf', file);

    try {
      const response = await axios.post(`${API_BASE_URL}/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });

      console.log('Upload response:', response.data);
      await fetchDocuments(); // Refresh the document list
      alert('PDF uploaded successfully!');
    } catch (error) {
      console.error('Upload error:', error);
      alert('Failed to upload PDF');
    } finally {
      setIsUploading(false);
      fileInputRef.current.value = ''; // Clear the file input
    }
  };

  // --- New Function: Toggle Document Selection ---
  const toggleDocumentSelection = (docId) => {
    setSelectedDocumentIds(prev => {
      if (prev.includes(docId)) {
        // If already selected, remove it
        return prev.filter(id => id !== docId);
      } else {
        // If not selected, add it
        return [...prev, docId];
      }
    });
  };

  // --- New Function: Clear All Document Selections ---
  const clearDocumentSelection = () => {
    setSelectedDocumentIds([]);
  };

  const handleSendMessage = async () => {
    // Prevent sending if input is empty, already loading, or no session is selected
    if (!inputMessage.trim() || isLoading || !currentSessionId) return;

    const userMessage = {
        role: 'user',
        content: inputMessage,
        timestamp: new Date().toISOString() // Add a timestamp
    };
    // Optimistically update the UI with the user's message
    setMessages(prev => [...prev, userMessage]);
    setInputMessage(''); // Clear the input field
    setIsLoading(true);

    try {
      // --- Pass session_id AND selected document_ids ---
      const requestBody = {
        message: inputMessage,
        session_id: currentSessionId,
        // Send selectedDocumentIds, or null/undefined if none selected (meaning search all)
        // Sending an empty array [] usually means "search none", so we send null for "search all"
        document_ids: selectedDocumentIds.length > 0 ? selectedDocumentIds : null
      };

      const response = await axios.post(`${API_BASE_URL}/chat`, requestBody);

      // The backend now returns only the new bot message object
      const botMessage = {
        role: 'assistant',
        content: response.data.content || response.data.answer, // Handle potential key change
        sources: response.data.sources,
        confidence: response.data.confidence,
        timestamp: response.data.timestamp || new Date().toISOString()
      };

      // Update the UI with the bot's response
      setMessages(prev => [...prev, botMessage]);
      // Session history is managed and persisted on the backend

      // Refresh session list to update message counts/titles if needed
      // fetchSessions();

    } catch (error) {
      console.error('Chat error:', error);
      const errorMessage = {
        role: 'assistant',
        content: 'Sorry, I encountered an error processing your request.'
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSendMessage();
    }
  };

  // --- UI Rendering ---
  return (
    <div className="app">
      <header className="header">
        <h1>🤖 SC4.0 AI Chatbot</h1>
        <div className="header-controls">
          <button
            onClick={createNewSession}
            disabled={isCreatingSession || isLoading}
            className="new-chat-button"
          >
            {isCreatingSession ? 'Creating...' : 'New Chat'}
          </button>
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileUpload}
            accept=".pdf"
            style={{ display: 'none' }}
          />
          <button
            onClick={() => fileInputRef.current.click()}
            disabled={isUploading || isLoading}
            className="upload-button"
          >
            {isUploading ? 'Uploading...' : 'Upload PDF'}
          </button>
        </div>
      </header>

      <div className="main-content">
        <div className="sidebar">
          {/* --- Modified Document Section with Selection UI --- */}
          <div className="documents-section">
            <div className="sidebar-section-header">
              <h3>Uploaded Documents ({documents.length})</h3>
              {documents.length > 0 && (
                <div className="document-selection-controls">
                  <span className="selected-count">
                    {selectedDocumentIds.length > 0 ? `${selectedDocumentIds.length} selected` : 'None selected'}
                  </span>
                  <button
                    onClick={clearDocumentSelection}
                    className="clear-selection-button"
                    disabled={selectedDocumentIds.length === 0}
                    title="Clear document selection"
                  >
                    Clear
                  </button>
                </div>
              )}
            </div>
            {documents.length === 0 ? (
              <p className="no-documents">No documents uploaded yet</p>
            ) : (
              <ul className="document-list">
                {documents.map(doc => {
                  const isSelected = selectedDocumentIds.includes(doc.id);
                  return (
                    <li
                      key={doc.id}
                      className={`document-item ${isSelected ? 'selected' : ''}`}
                      onClick={() => toggleDocumentSelection(doc.id)} // Click item to toggle
                    >
                      <div className="document-info">
                        <span className="document-name">📄 {doc.name}</span>
                        <span className="chunk-count">({doc.chunks_count} chunks)</span>
                      </div>
                      {/* Checkbox for visual confirmation and alternative interaction */}
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => {}} // Handled by onClick on the li
                        className="document-checkbox"
                        onClick={(e) => e.stopPropagation()} // Prevent li click from triggering twice
                      />
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          {/* --- Chat History Section (existing) --- */}
          <div className="chat-history-section">
            <div className="chat-history-header">
              <h3>Chat History</h3>
              <button onClick={fetchSessions} className="refresh-button" title="Refresh chat list">
                ↻
              </button>
            </div>
            {sessions.length === 0 ? (
              <p className="no-sessions">No chat sessions yet</p>
            ) : (
              <ul className="session-list">
                {sessions.map(session => (
                  <li
                    key={session.session_id}
                    className={`session-item ${session.session_id === currentSessionId ? 'active' : ''}`}
                    onClick={() => loadSession(session.session_id)}
                  >
                    <div className="session-title">{session.title}</div>
                    <div className="session-meta">
                      <span className="session-date">
                        {new Date(session.created_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                      </span>
                      <span className="message-count">({session.message_count} msgs)</span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <div className="chat-container">
          {/* Session Info Bar */}
          {currentSessionId && (
            <div className="session-info">
              <span>Session: {currentSessionId.substring(0, 8)}...</span>
              {/* Add delete session button here if needed */}
            </div>
          )}

          <div className="messages">
            {messages.length === 0 ? (
              <div className="welcome-message">
                <h2>Welcome to SC4.0 AI Chatbot!</h2>
                {currentSessionId ? (
                  <>
                    <p>Start a conversation by typing a message below.</p>
                  </>
                ) : (
                  <>
                    <p>Select a chat session or start a new one.</p>
                    <button onClick={createNewSession} className="start-chat-button">
                      Start New Chat
                    </button>
                  </>
                )}
                <div className="instructions">
                  <h3>How to use:</h3>
                  <ol>
                    <li>Click "Upload PDF" to add documents</li>
                    <li>Select an existing chat or start a "New Chat"</li>
                    <li>Ask questions in the chat box below</li>
                    <li>Get answers with source references</li>
                  </ol>
                </div>
              </div>
            ) : (
              messages.map((message, index) => (
                <div key={index} className={`message ${message.role}`}>
                  <div className="message-content">
                    {message.content}
                  </div>
                  {message.sources && message.sources.length > 0 && (
                    <div className="sources">
                      <h4>Sources:</h4>
                      {message.sources.map((source, idx) => (
                        <div key={idx} className="source-item">
                          <strong>{source.source}</strong>
                          <p>{source.content}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))
            )}
            {isLoading && (
              <div className="message assistant">
                <div className="message-content typing-indicator">
                  🤖 Thinking...
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="input-area">
            {!currentSessionId ? (
              <div className="select-session-prompt">
                <p>Please select a chat session or start a new one to begin chatting.</p>
              </div>
            ) : (
              <>
                <textarea
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="Ask a question about your documents..."
                  disabled={isLoading}
                  rows="3"
                />
                <button
                  onClick={handleSendMessage}
                  disabled={!inputMessage.trim() || isLoading}
                  className="send-button"
                >
                  Send
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
