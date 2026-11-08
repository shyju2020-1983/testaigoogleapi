import React, { useState, useEffect, useRef } from 'react';

function App() {
  const [query, setQuery] = useState('');
  // Stores the array of conversation pairs: [{ question: "...", answer: "..." }]
  const [chatHistory, setChatHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  
  // Create a reference to automatically scroll to the newest inputs
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [chatHistory, loading]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    const currentQuery = query;
    setQuery(''); // Clear the input field instantly for a responsive feel
    setLoading(true);

    const targetUrl = 'http://localhost:8000/api/query';

    try {
      const res = await fetch(targetUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: currentQuery }),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || `Server status error: ${res.status}`);
      }

      const data = await res.json();

      if (data && data.answer) {
        // Strip markdown asterisks on the frontend
        const cleanAnswer = String(data.answer).replace(/\*\*/g, '');
        
        // Append the new question and clean answer to the history list
        setChatHistory((prev) => [...prev, { question: currentQuery, answer: cleanAnswer }]);
      } else {
        setChatHistory((prev) => [
          ...prev, 
          { question: currentQuery, answer: 'Error: Received empty or unmappable response payload.' }
        ]);
      }
    } catch (error) {
      console.error("Network bridge failure detail:", error);
      setChatHistory((prev) => [
        ...prev, 
        { question: currentQuery, answer: `Error: ${error.message || 'Failed to connect to backend.'}` }
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ backgroundColor: '#121212', minHeight: '100vh', width: '100%', padding: '40px 0', boxSizing: 'border-box' }}>
      <div style={{ maxWidth: '600px', margin: '0 auto', padding: '20px', fontFamily: 'sans-serif', color: '#ffffff' }}>
        
        <h2 style={{ borderBottom: '1px solid #333', paddingBottom: '10px' }}>
          <b>Kadirur village chat bot</b>
        </h2>
        
        {/* CHAT DISPLAY LOG PANEL */}
        <div style={{ marginTop: '20px' }}>
          {chatHistory.map((chat, index) => (
            <div key={index} style={{ marginBottom: '25px' }}>
              
              {/* User Question Box */}
              <div style={{ background: '#222', padding: '12px', borderRadius: '6px', marginBottom: '8px', border: '1px solid #444' }}>
                <strong style={{ color: '#aaa', fontSize: '12px' }}>Your Question:</strong>
                <p style={{ margin: '5px 0 0 0', color: '#fff', fontSize: '15px' }}>{chat.question}</p>
              </div>

              {/* AI Answer Box */}
              <div style={{ background: '#1e1e1e', padding: '15px', borderRadius: '6px', border: '1px solid #333' }}>
                <strong style={{ color: '#007bff', fontSize: '12px' }}>Answer Output:</strong>
                <p style={{ whiteSpace: 'pre-wrap', marginTop: '5px', marginBottom: '0', color: '#e0e0e0', fontWeight: '500', lineHeight: '1.5', fontSize: '15px' }}>
                  {chat.answer}
                </p>
              </div>

            </div>
          ))}

          {/* Inline Loading / Processing State Indicator Box */}
          {loading && (
            <div style={{ background: '#1e1e1e', padding: '15px', borderRadius: '6px', border: '1px solid #333', marginBottom: '25px' }}>
              <strong style={{ color: '#007bff', fontSize: '12px' }}>Answer Output:</strong>
              <p style={{ marginTop: '5px', marginBottom: '0', color: '#888', fontStyle: 'italic' }}>
                Thinking...
              </p>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        {/* PERSISTENT INPUT ROW SITUATED DIRECTLY BENEATH GENERATED RESPONSES */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '10px', marginTop: '20px', position: 'sticky', bottom: '20px', backgroundColor: '#121212', padding: '10px 0' }}>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={chatHistory.length > 0 ? "Ask a follow-up question..." : "Ask a question about your text file..."}
            style={{ flexGrow: 1, padding: '12px', fontSize: '15px', backgroundColor: '#222', border: '1px solid #444', color: '#fff', borderRadius: '6px', outline: 'none' }}
            disabled={loading}
          />
          <button 
            type="submit" 
            disabled={loading} 
            style={{ padding: '0 24px', cursor: 'pointer', backgroundColor: '#007bff', color: '#fff', border: 'none', borderRadius: '6px', fontWeight: 'bold', fontSize: '15px' }}
          >
            Ask
          </button>
        </form>

      </div>
    </div>
  );
}

export default App;
