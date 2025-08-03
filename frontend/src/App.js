// frontend/src/App.js

import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import './App.css';

const API_BASE_URL = 'http://localhost:5000/api';

function App() {
  // --- State Management ---
  const [documents, setDocuments] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isCreatingSession, setIsCreatingSession] = useState(false);
  const [isDeletingSession, setIsDeletingSession] = useState({});
  const [isDeletingDocument, setIsDeletingDocument] = useState({});
  const [selectedDocumentIds, setSelectedDocumentIds] = useState([]);
  const [availableModels, setAvailableModels] = useState([]);
  const [currentModel, setCurrentModel] = useState('');
  const [isChangingModel, setIsChangingModel] = useState(false);

  // --- State for Speech Features ---
  const [isListening, setIsListening] = useState(false);
  const [ttsState, setTtsState] = useState('idle'); // 'idle', 'speaking', 'paused'
  const [ttsSupported, setTtsSupported] = useState(false);
  const [sttSupported, setSttSupported] = useState(false);
  // --- End State for Speech Features ---

  // --- State for Context Menu ---
  const [contextMenuVisible, setContextMenuVisible] = useState(false);
  const [contextMenuSessionId, setContextMenuSessionId] = useState(null);
  const [contextMenuPosition, setContextMenuPosition] = useState({ x: 0, y: 0 });
  // --- End State for Context Menu ---

  const fileInputRef = useRef(null);
  const messagesEndRef = useRef(null);
  const contextMenuRef = useRef(null);
  // --- Refs for Speech ---
  const recognitionRef = useRef(null);
  const utteranceRef = useRef(null);
  // --- End Refs for Speech ---

  // --- Check for Web Speech API Support ---
  useEffect(() => {
    if ('speechSynthesis' in window) {
      setTtsSupported(true);
      console.log("Text-to-Speech (Web Speech API) is supported.");
    } else {
      console.warn("Text-to-Speech (Web Speech API) is not supported.");
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      setSttSupported(true);
      console.log("Speech-to-Text (Web Speech API) is supported.");
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = 'en-US';

      recognition.onresult = (event) => {
        let transcript = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
          transcript += event.results[i][0].transcript;
        }
        setInputMessage(transcript);
      };

      recognition.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        setIsListening(false);
      };

      recognition.onend = () => {
        console.log("Speech recognition ended.");
        setIsListening(false);
      };

      recognitionRef.current = recognition;
    } else {
      console.warn("Speech-to-Text (Web Speech API) is not supported.");
    }
  }, []);

  // --- Cleanup Speech ---
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      if (utteranceRef.current && window.speechSynthesis.speaking) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  // --- Auto-scroll messages ---
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // --- Close context menu on outside click ---
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (contextMenuRef.current && !contextMenuRef.current.contains(event.target)) {
        closeContextMenu();
      }
    };

    if (contextMenuVisible) {
      document.addEventListener('mousedown', handleClickOutside);
    } else {
      document.removeEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [contextMenuVisible]);

  // --- Fetch initial data ---
  useEffect(() => {
    const initializeApp = async () => {
      try {
        await Promise.all([
          fetchDocuments(),
          fetchSessions(),
          fetchModels()
        ]);
      } catch (error) {
        console.error("Error during initialization:", error);
      }
    };

    initializeApp();
  }, []);

  // --- API Calls ---
  const fetchDocuments = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/documents`);
      setDocuments(response.data);
    } catch (error) {
      console.error('Error fetching documents:', error);
    }
  };

  const fetchSessions = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/sessions`);
      setSessions(response.data);
    } catch (error) {
      console.error('Error fetching sessions:', error);
    }
  };

  const createNewSession = async () => {
    setIsCreatingSession(true);
    try {
      const response = await axios.post(`${API_BASE_URL}/sessions`);
      const newSessionId = response.data.session_id;
      setCurrentSessionId(newSessionId);
      setMessages([]);
      setSelectedDocumentIds([]);
      await fetchSessions();
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
      setMessages(response.data.session.messages || []);
      setSelectedDocumentIds([]);
      console.log("Loaded session:", sessionId);
    } catch (error) {
      console.error('Error loading session:', error);
      alert('Failed to load chat session.');
    }
  };

  // --- Updated handleFileUpload for PDFs and Images ---
  const handleFileUpload = async (event) => {
    const files = Array.from(event.target.files);
    if (files.length === 0) return;

    // --- Update allowed file types ---
    const allowedTypes = ['application/pdf', 'image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/bmp', 'image/tiff', 'image/webp'];
    const invalidFiles = files.filter(file => !allowedTypes.includes(file.type));
    if (invalidFiles.length > 0) {
        alert(`Please upload only PDF or image files. Invalid files: ${invalidFiles.map(f => f.name).join(', ')}`);
        if (fileInputRef.current) fileInputRef.current.value = '';
        return;
    }
    // --- End Update allowed file types ---

    setIsUploading(true);
    const uploadPromises = [];

    for (const file of files) {
        const formData = new FormData();
        // --- Determine endpoint and form field based on file type ---
        let uploadUrl = `${API_BASE_URL}/upload`; // Default to PDF endpoint
        let fieldName = 'pdf'; // Default field name for PDF

        if (file.type.startsWith('image/')) {
            uploadUrl = `${API_BASE_URL}/upload/image`; // Use image endpoint
            fieldName = 'image'; // Use 'image' field name
        }
        formData.append(fieldName, file);
        // --- End Determine endpoint ---

        // Create a promise for each upload
        const uploadPromise = axios.post(uploadUrl, formData, {
            headers: {
                'Content-Type': 'multipart/form-data'
            }
        }).then(response => {
            console.log(`Upload response for ${file.name}:`, response.data);
            return { success: true, filename: file.name, data: response.data };
        }).catch(error => {
            console.error(`Upload error for ${file.name}:`, error);
            return { success: false, filename: file.name, error: error.message };
        });

        uploadPromises.push(uploadPromise);
    }

    try {
        const results = await Promise.all(uploadPromises);
        const successfulUploads = results.filter(r => r.success);
        const failedUploads = results.filter(r => !r.success);

        if (successfulUploads.length > 0) {
            await fetchDocuments(); // Refresh the document list once after all uploads
            alert(`Successfully uploaded ${successfulUploads.length} file(s).`);
        }

        if (failedUploads.length > 0) {
            alert(`Failed to upload ${failedUploads.length} file(s):\n${failedUploads.map(f => `- ${f.filename}: ${f.error}`).join('\n')}`);
        }
    } finally {
        setIsUploading(false);
        if (fileInputRef.current) fileInputRef.current.value = ''; // Clear the file input
    }
  };
  // --- End Updated handleFileUpload ---

  const toggleDocumentSelection = (docId) => {
    setSelectedDocumentIds(prev => {
      if (prev.includes(docId)) {
        return prev.filter(id => id !== docId);
      } else {
        return [...prev, docId];
      }
    });
  };

  // --- New Function: Select/Deselect All Documents ---
  const toggleSelectAllDocuments = () => {
    if (selectedDocumentIds.length === documents.length) {
      // If all are selected, deselect all
      setSelectedDocumentIds([]);
    } else {
      // If not all are selected, select all
      setSelectedDocumentIds(documents.map(doc => doc.id));
    }
  };
  // --- End New Function ---

  const clearDocumentSelection = () => {
    setSelectedDocumentIds([]);
  };

  const fetchModels = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/models`);
      setAvailableModels(response.data.available_models || []);
      setCurrentModel(response.data.current_model || '');
      console.log("Fetched models:", response.data);
    } catch (error) {
      console.error('Error fetching models:', error);
    }
  };

  const changeModel = async (newModelName) => {
    if (!newModelName || newModelName === currentModel) return;
    setIsChangingModel(true);
    try {
      const response = await axios.post(`${API_BASE_URL}/models`, { model_name: newModelName });
      console.log("Model change response:", response.data);
      setCurrentModel(newModelName);
    } catch (error) {
      console.error('Error changing model:', error);
      if (error.response?.data?.error) {
        alert(`Failed to change model: ${error.response.data.error}`);
      } else {
        alert('Failed to change model. Please try again.');
      }
      await fetchModels();
    } finally {
      setIsChangingModel(false);
    }
  };

  const clearCurrentChat = () => {
    if (!currentSessionId) {
      setMessages([]);
      return;
    }
    setMessages([]);
    console.log(`Cleared chat messages for session ${currentSessionId}`);
  };

  // --- Context Menu Functions ---
  const openContextMenu = (e, sessionId) => {
    e.preventDefault();
    setContextMenuVisible(true);
    setContextMenuSessionId(sessionId);
    setContextMenuPosition({ x: e.clientX, y: e.clientY });
  };

  const closeContextMenu = () => {
    setContextMenuVisible(false);
    setContextMenuSessionId(null);
  };

  const renameSession = async () => {
    if (!contextMenuSessionId) return;
    const session = sessions.find(s => s.session_id === contextMenuSessionId);
    if (!session) return;

    const newName = prompt("Enter new session name:", session.title);
    if (newName !== null && newName.trim() !== "" && newName !== session.title) {
      try {
        await axios.put(`${API_BASE_URL}/sessions/${contextMenuSessionId}`, { title: newName.trim() });
        setSessions(prevSessions =>
          prevSessions.map(s =>
            s.session_id === contextMenuSessionId ? { ...s, title: newName.trim() } : s
          )
        );
        console.log(`Session ${contextMenuSessionId} renamed to: ${newName}`);
      } catch (error) {
        console.error('Error renaming session:', error);
        alert('Failed to rename session.');
      }
    }
    closeContextMenu();
  };

  const deleteSession = async (sessionIdToDelete) => {
    const idToDelete = sessionIdToDelete || contextMenuSessionId;
    if (!idToDelete) return;

    setIsDeletingSession(prev => ({ ...prev, [idToDelete]: true }));

    try {
      await axios.delete(`${API_BASE_URL}/sessions/${idToDelete}`);
      console.log("Delete session response:", idToDelete);

      setSessions(prevSessions => prevSessions.filter(s => s.session_id !== idToDelete));

      if (idToDelete === currentSessionId) {
        setCurrentSessionId(null);
        setMessages([]);
      }
      if (idToDelete === contextMenuSessionId) {
          closeContextMenu();
      }

    } catch (error) {
      console.error('Error deleting session:', error);
      if (error.response?.data?.error) {
        alert(`Failed to delete session: ${error.response.data.error}`);
      } else {
        alert('Failed to delete session. Please try again.');
      }
    } finally {
      setIsDeletingSession(prev => {
        const newState = { ...prev };
        delete newState[idToDelete];
        return newState;
      });
    }
  };
  // --- End Context Menu Functions ---

  const deleteDocument = async (docIdToDelete) => {
    if (!docIdToDelete) return;
    if (selectedDocumentIds.includes(docIdToDelete)) {
        setSelectedDocumentIds(prev => prev.filter(id => id !== docIdToDelete));
    }

    setIsDeletingDocument(prev => ({ ...prev, [docIdToDelete]: true }));

    try {
      // --- Call the DELETE endpoint ---
      const response = await axios.delete(`${API_BASE_URL}/documents/${docIdToDelete}`);
      console.log("Delete document response:", response.data);

      // Update local state
      setDocuments(prevDocs => prevDocs.filter(d => d.id !== docIdToDelete));
      // Optional: Show success message
      // alert('Document deleted.');

    } catch (error) {
      console.error('Error deleting document (frontend):', error);
      // Show user-friendly error
      if (error.response?.data?.error) {
        alert(`Failed to delete document: ${error.response.data.error}`);
      } else {
        alert('Failed to delete document. Please try again.');
      }
    } finally {
      setIsDeletingDocument(prev => {
        const newState = { ...prev };
        delete newState[docIdToDelete];
        return newState;
      });
    }
  };


  // --- Speech Functions ---
  const startListening = () => {
    if (!sttSupported || !recognitionRef.current) {
      alert("Speech-to-Text is not supported.");
      return;
    }
    if (isListening) return;

    try {
      setInputMessage('');
      recognitionRef.current.start();
      setIsListening(true);
      console.log("Started listening...");
    } catch (error) {
      console.error("Error starting speech recognition:", error);
      setIsListening(false);
      alert("Failed to start speech recognition. Please check permissions.");
    }
  };

  const stopListening = () => {
    if (!sttSupported || !recognitionRef.current || !isListening) return;

    try {
      recognitionRef.current.stop();
      setIsListening(false);
      console.log("Stopped listening.");
    } catch (error) {
      console.error("Error stopping speech recognition:", error);
    }
  };

  const speakText = (text) => {
    if (!ttsSupported) {
      alert("Text-to-Speech is not supported.");
      return;
    }
    if (!text) return;

    try {
      if (window.speechSynthesis.speaking) {
        window.speechSynthesis.cancel();
      }

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = 'en-US';
      utterance.rate = 1;
      utterance.pitch = 1;
      utterance.volume = 1;

      utterance.onstart = () => {
        setTtsState('speaking');
        console.log("Started speaking...");
      };

      utterance.onend = () => {
        setTtsState('idle');
        console.log("Finished speaking.");
      };

      utterance.onerror = (event) => {
        console.error("Speech synthesis error:", event);
        setTtsState('idle');
      };

      utteranceRef.current = utterance;
      window.speechSynthesis.speak(utterance);
    } catch (error) {
      console.error("Error initiating speech synthesis:", error);
      setTtsState('idle');
      alert("Failed to speak text.");
    }
  };

  const pauseTts = () => {
    if (window.speechSynthesis.speaking && !window.speechSynthesis.paused) {
      window.speechSynthesis.pause();
      setTtsState('paused');
      console.log("Paused speaking.");
    }
  };

  const resumeTts = () => {
    if (window.speechSynthesis.paused) {
      window.speechSynthesis.resume();
      setTtsState('speaking');
      console.log("Resumed speaking.");
    }
  };

  const stopTts = () => {
    if (window.speechSynthesis.speaking) {
      window.speechSynthesis.cancel();
      setTtsState('idle');
      console.log("Stopped speaking.");
    }
  };
  // --- End Speech Functions ---

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isLoading || !currentSessionId) return;

    const userMessage = {
        role: 'user',
        content: inputMessage,
        timestamp: new Date().toISOString()
    };
    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);

    try {
      const requestBody = {
        message: inputMessage,
        session_id: currentSessionId,
        document_ids: selectedDocumentIds.length > 0 ? selectedDocumentIds : null
      };

      const response = await axios.post(`${API_BASE_URL}/chat`, requestBody);

      const botMessage = {
        role: 'assistant',
        content: response.data.content || response.data.answer,
        sources: response.data.sources,
        confidence: response.data.confidence,
        timestamp: response.data.timestamp || new Date().toISOString()
      };

      setMessages(prev => [...prev, botMessage]);

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
          {/* --- Model Selector Dropdown --- */}
          <div className="model-selector">
            <label htmlFor="model-select">Model:</label>
            <select
              id="model-select"
              value={currentModel}
              onChange={(e) => changeModel(e.target.value)}
              disabled={isChangingModel || isLoading || isCreatingSession || isUploading}
              className="model-dropdown"
            >
              {availableModels.length > 0 ? (
                availableModels.map((model) => (
                  <option key={model} value={model}>
                    {model}
                  </option>
                ))
              ) : (
                <option value="">Loading models...</option>
              )}
            </select>
            {isChangingModel && <span className="changing-indicator">Changing...</span>}
          </div>
          {/* --- End Model Selector --- */}


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
            // --- Update accepted file types ---
            accept=".pdf,image/*" // Accept PDFs and all image types
            // --- End Update accepted file types ---
            multiple // Allow multiple file selection
            style={{ display: 'none' }}
          />
          <button
            onClick={() => fileInputRef.current.click()}
            disabled={isUploading || isLoading}
            className="upload-button"
          >
            {isUploading ? 'Uploading...' : 'Upload Files'} {/* Updated button text */}
          </button>
        </div>
      </header>

      <div className="main-content">
        <div className="sidebar">
          {/* --- Modified Document Section with Selection UI and Delete --- */}
          <div className="documents-section">
            <div className="sidebar-section-header">
              <h3>Uploaded Documents ({documents.length})</h3>
              {documents.length > 0 && (
                <div className="document-selection-controls">
                  {/* --- Select All Checkbox --- */}
                  <label className="select-all-label">
                    <input
                      type="checkbox"
                      checked={selectedDocumentIds.length === documents.length && documents.length > 0}
                      onChange={toggleSelectAllDocuments}
                      className="select-all-checkbox"
                    />
                  </label>
                  {/* --- End Select All Checkbox --- */}
                </div>
              )}
            </div>
            {documents.length === 0 ? (
              <p className="no-documents">No documents uploaded yet</p>
            ) : (
              <ul className="document-list">
                {documents.map(doc => {
                  const isSelected = selectedDocumentIds.includes(doc.id);
                  const isDeleting = isDeletingDocument[doc.id] || false;
                  return (
                    <li
                      key={doc.id}
                      className={`document-item ${isSelected ? 'selected' : ''}`}
                      onClick={() => toggleDocumentSelection(doc.id)}
                    >
                      <div className="document-info">
                        {/* --- Add icon based on type --- */}
                        <span className="document-name">
                          {doc.type === 'image' ? '🖼️' : '📄'} {doc.name}
                        </span>
                        {/* --- End Add icon --- */}
                        <span className="chunk-count">({doc.chunks_count} chunks)</span>
                      </div>
                      <div className="document-actions">
                        {/* --- Individual Checkbox --- */}
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => {}} // Handled by onClick on the li
                          className="document-checkbox"
                          onClick={(e) => e.stopPropagation()}
                        />
                        {/* --- End Individual Checkbox --- */}
                        <button
                          className="delete-button"
                          onClick={(e) => {
                            e.stopPropagation();
                            if (window.confirm(`Are you sure you want to delete '${doc.name}'?`)) {
                              deleteDocument(doc.id);
                            }
                          }}
                          disabled={isDeleting}
                          aria-label={`Delete document ${doc.name}`}
                        >
                          {isDeleting ? 'Deleting...' : '🗑️'}
                        </button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          {/* --- Modified Chat History Section with Delete --- */}
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
                {sessions.map(session => {
                 const isDeleting = isDeletingSession[session.session_id] || false;
                 const isActive = session.session_id === currentSessionId;
                 return (
                  <li
                    key={session.session_id}
                    className={`session-item ${isActive ? 'active' : ''}`}
                    onClick={() => !isDeleting && loadSession(session.session_id)}
                    onContextMenu={(e) => openContextMenu(e, session.session_id)}
                  >
                    <div className="session-info" onClick={(e) => e.stopPropagation()}>
                      <div className="session-title">{session.title}</div>
                      <div className="session-meta">
                        <span className="session-date">
                          {new Date(session.created_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                        </span>
                        <span className="message-count">({session.message_count} msgs)</span>
                      </div>
                    </div>
                    <button
                      className="context-menu-button"
                      onClick={(e) => {
                        e.stopPropagation();
                        openContextMenu(e, session.session_id);
                      }}
                      aria-label={`Menu for session ${session.title}`}
                      title="Session options"
                    >
                      ⋮
                    </button>
                  </li>
                 );
                })}
              </ul>
            )}
          </div>
        </div>

        {/* Context Menu Popup */}
        {contextMenuVisible && (
          <div
            ref={contextMenuRef}
            className="context-menu"
            style={{
              position: 'fixed',
              top: contextMenuPosition.y,
              left: contextMenuPosition.x,
              zIndex: 1000,
            }}
          >
            <button onClick={renameSession} aria-label="Rename session">
              🖊️ Rename
            </button>
            <button
              onClick={() => {
                const session = sessions.find(s => s.session_id === contextMenuSessionId);
                const sessionTitle = session ? session.title : 'this session';
                if (window.confirm(`Are you sure you want to delete chat session '${sessionTitle}'?`)) {
                  deleteSession(contextMenuSessionId);
                } else {
                  closeContextMenu(); // Close menu if user cancels
                }
              }}
              aria-label="Delete session"
            >
              🗑️ Delete
            </button>
          </div>
        )}
        {/* End Context Menu Popup */}

        <div className="chat-container">
          {/* --- Modified Session Info Bar to include Clear and Delete Chat Buttons --- */}
          {currentSessionId && (
            <div className="session-info-bar">
              <div className="session-info">
                <span>Session: {currentSessionId.substring(0, 8)}...</span>
              </div>
              <div className="chat-controls">
                <button
                  onClick={clearCurrentChat}
                  disabled={isLoading}
                  className="clear-chat-button"
                  title="Clear messages in this chat"
                >
                  Clear Chat
                </button>
                <button
                  onClick={() => {
                    const currentSession = sessions.find(s => s.session_id === currentSessionId);
                    const sessionTitle = currentSession ? currentSession.title : 'this session';
                    if (window.confirm(`Are you sure you want to delete the entire chat session '${sessionTitle}'?`)) {
                      deleteSession(currentSessionId);
                    }
                  }}
                  disabled={isLoading || isDeletingSession[currentSessionId]}
                  className="delete-session-button"
                  title="Delete this entire chat session"
                >
                  {isDeletingSession[currentSessionId] ? 'Deleting...' : 'Delete Chat'}
                </button>
              </div>
            </div>
          )}
          {/* --- End Modified Session Info Bar --- */}

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
                    <li>Click "Upload Files" to add PDFs or images</li>
                    <li>Select documents to filter questions (optional)</li>
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

                  {/* --- Add Text-to-Speech Controls --- */}
                  {message.role === 'assistant' && ttsSupported && (
                    <div className="tts-controls">
                      {ttsState === 'speaking' ? (
                        <>
                          <button
                            className="tts-control-button pause"
                            onClick={pauseTts}
                            aria-label="Pause reading"
                            title="Pause reading"
                          >
                            ⏸️
                          </button>
                          <button
                            className="tts-control-button stop"
                            onClick={stopTts}
                            aria-label="Stop reading"
                            title="Stop reading"
                          >
                            ⏹️
                          </button>
                        </>
                      ) : ttsState === 'paused' ? (
                        <>
                          <button
                            className="tts-control-button play"
                            onClick={resumeTts}
                            aria-label="Resume reading"
                            title="Resume reading"
                          >
                            ▶️
                          </button>
                          <button
                            className="tts-control-button stop"
                            onClick={stopTts}
                            aria-label="Stop reading"
                            title="Stop reading"
                          >
                            ⏹️
                          </button>
                        </>
                      ) : (
                        <button
                          className="tts-control-button play"
                          onClick={() => speakText(message.content)}
                          aria-label="Read message aloud"
                          title="Read this message aloud"
                        >
                          🔊
                        </button>
                      )}
                    </div>
                  )}
                  {/* --- End Text-to-Speech Controls --- */}

                  {message.sources && message.sources.length > 0 && (
                    <div className="sources">
                      <h4>Sources:</h4>
                      <ul className="source-list">
                        {message.sources.map((source, idx) => (
                          <li key={idx} className="source-item">
                            <sup className="source-number">[{idx + 1}]</sup>
                            <div className="source-details">
                              <strong className="source-name">{source.source}</strong>
                              <p className="source-snippet" title={source.content}>{source.content}</p>
                            </div>
                          </li>
                        ))}
                      </ul>
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
                <div className="input-and-stt">
                  <textarea
                    value={inputMessage}
                    onChange={(e) => setInputMessage(e.target.value)}
                    onKeyPress={handleKeyPress}
                    placeholder="Ask a question about your documents..."
                    disabled={isLoading || isListening}
                    rows="3"
                  />
                  {/* --- Speech-to-Text Button (In Input Area) --- */}
                  {sttSupported && (
                    <button
                      onClick={isListening ? stopListening : startListening}
                      className={`speech-button stt-button-in-input ${isListening ? 'listening' : ''}`}
                      aria-label={isListening ? "Stop listening" : "Start voice input"}
                      title={isListening ? "Stop listening" : "Start voice input"}
                      disabled={isLoading}
                    >
                      {isListening ? '🛑' : '🎤'}
                    </button>
                  )}
                  {/* --- End Speech-to-Text Button --- */}
                </div>
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
