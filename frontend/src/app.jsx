import React, { useState, useEffect, useRef } from 'react';

function App() {
  const [query, setQuery] = useState('');
  const [chatHistory, setChatHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [errorDetails, setErrorDetails] = useState(null);

  // ANIMATED LIGHT BLUE PLACEHOLDER ROTATION STATES
  const [placeholderText, setPlaceholderText] = useState('Ask question about kadirur');
  const [followUpPlaceholder, setFollowUpPlaceholder] = useState('Ask follow-up question');

  useEffect(() => {
    let isEnglish = true;

    const interval = setInterval(() => {
      isEnglish = !isEnglish;

      if (isEnglish) {
        setPlaceholderText('Ask question about Kadirur');
        setFollowUpPlaceholder('Ask follow-up question');
      } else {
        setPlaceholderText('കതിരൂരിനെക്കുറിച്ച് ചോദ്യം ചോദിക്കാം');
        setFollowUpPlaceholder('വീണ്ടും തുടർച്ചോദ്യങ്ങൾ ചോദിക്കാം');
      }
    }, 2000);

    return () => clearInterval(interval);
  }, []);

  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [chatHistory, loading, errorDetails]);

  const linkify = (text) =>
    text?.split(/(https?:\/\/[^\s<>"']+)/g).map((part, i) => {
      if (!part.startsWith('http')) return part;
      const cleanUrl = part.replace(/[\]'.,;!?]+$/, '');
      return (
        <a
          key={i}
          href={cleanUrl}
          target="_blank"
          rel="noopener noreferrer"
          style={{ color: '#90caf9', textDecoration: 'underline', wordBreak: 'break-all' }}
        >
          {cleanUrl}
        </a>
      );
    });

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    const currentQuery = query;
    setQuery('');
    setLoading(true);
    setErrorDetails(null);

    const ec2PublicIp = "13.233.119.28";
    const targetUrl = `http://${ec2PublicIp}:8000/api/query`;

    // Below code for local running 
// const targetUrl = 'http://localhost:8000/api/query';
    try {
      const res = await fetch(targetUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: currentQuery }),
      });

      if (!res.ok) {
        throw new Error(`HTTP Error Status: ${res.status} - ${res.statusText}`);
      }

      const data = await res.json();

      if (data && data.answer) {
        const cleanAnswer = String(data.answer).replace(/\*\*/g, '');
        setChatHistory((prev) => [...prev, { question: currentQuery, answer: cleanAnswer }]);
      } else {
        setChatHistory((prev) => [
          ...prev,
          { question: currentQuery, answer: 'Error: Received empty or unmappable response payload.' }
        ]);
      }
    } catch (error) {
      console.error("Network bridge failure detail:", error);
      setErrorDetails({
        name: error.name,
        message: error.message,
        targetUrl: targetUrl,
        hint: "1. Confirm 'python3 app.py' is active on EC2. 2. Verify Security Groups accept Port 8000. 3. Access the S3 link over http:// rather than https:// to prevent Mixed Content protocol drops."
      });
    } finally {
      setLoading(false);
    }
  };

  const handleClearChat = () => {
    setChatHistory([]);
    setErrorDetails(null);
    setQuery('');
  };

  return (
    <div style={{ backgroundColor: '#121212', minHeight: '100vh', width: '100%', padding: '40px 0', boxSizing: 'border-box' }}>
      <style>{`
        .custom-chat-input::placeholder {
          color: #90caf9 !important;
          opacity: 0.85;
        }
      `}</style>

      <div style={{ maxWidth: '600px', margin: '0 auto', padding: '20px', fontFamily: 'sans-serif', color: '#ffffff' }}>
        <h2 style={{ paddingBottom: '10px', textAlign: 'center', color: '#007bff' }}>
          <b>Kadirur village chatbot</b>
        </h2>

        {/* CHAT DISPLAY LOG PANEL */}
        <div style={{ marginTop: '20px' }}>
          {chatHistory.map((chat, index) => {
            const parts = chat.answer.split(/\n?\s*---\s*\n?/);
            const englishReply = parts[0] ? parts[0].trim() : '';
            const malayalamReply = parts[1] ? parts[1].trim() : '';

            return (
              <div key={index} style={{ marginBottom: '25px' }}>
                {/* User Question Box */}
                <div style={{ background: '#222', padding: '12px', borderRadius: '6px', marginBottom: '8px', border: '1px solid #444' }}>
                  <strong style={{ color: '#007bff', fontSize: '12px' }}>Your Question:</strong>
                  <p style={{ margin: '5px 0 0 0', color: '#fff', fontSize: '15px' }}>{chat.question}</p>
                </div>

                {/* AI Answer Box Layout Wrapper */}
                <div style={{ background: '#1e1e1e', padding: '15px', borderRadius: '6px', border: '1px solid #333' }}>
                  {/* English Response Container Block */}
                  <strong style={{ color: '#007bff', fontSize: '12px' }}>English Response:</strong>
                  <p style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', marginTop: '5px', marginBottom: '0', color: '#e0e0e0', fontWeight: '500', lineHeight: '1.5', fontSize: '15px' }}>
                    {linkify(englishReply || chat.answer)}
                  </p>

                  {/* Malayalam response section */}
                  {malayalamReply && (
                    <>
                      <hr style={{ border: 'none', borderTop: '1px solid #333', margin: '15px 0' }} />
                      <strong style={{ color: '#007bff', fontSize: '12px', display: 'block', marginBottom: '5px' }}>മലയാളം മറുപടി:</strong>
                      <p style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', margin: '0', color: '#e0e0e0', fontWeight: '500', lineHeight: '1.5', fontSize: '15px' }}>
                        {linkify(malayalamReply)}
                      </p>
                    </>
                  )}
                </div>
              </div>
            );
          })}

          {errorDetails && (
            <div style={{ marginTop: '24px', padding: '16px', backgroundColor: '#2d1a1a', border: '1px solid #c53030', borderRadius: '6px', color: '#fc8181' }}>
              <h4 style={{ margin: '0 0 8px 0', fontSize: '16px', color: '#fff' }}>⚠️ Network Intercept Failure</h4>
              <p style={{ margin: '4px 0', fontSize: '14px' }}><strong>Fault Type:</strong> {errorDetails.name}</p>
              <p style={{ margin: '4px 0', fontSize: '14px' }}><strong>Message:</strong> {errorDetails.message}</p>
              <p style={{ margin: '4px 0', fontSize: '14px' }}><strong>Target URL:</strong> <code>{errorDetails.targetUrl}</code></p>
              <p style={{ margin: '12px 0 0 0', fontSize: '12.5px', color: '#cbd5e0', borderTop: '1px dashed #c53030', paddingTop: '8px', lineHeight: '1.4' }}>
                {errorDetails.hint}
              </p>
            </div>
          )}

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

        {/* PERSISTENT INPUT ROW */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '10px', marginTop: '20px', position: 'sticky', bottom: '20px', backgroundColor: '#121212', padding: '10px 0' }}>
          <input
            type="text"
            className="custom-chat-input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={(chatHistory.length > 0 || loading) ? followUpPlaceholder : placeholderText}
            disabled={loading}
            style={{
              flexGrow: 1,
              padding: '12px',
              fontSize: '15px',
              backgroundColor: '#222',
              border: '1px solid #444',
              color: '#fff',
              borderRadius: '6px',
              outline: 'none',
              opacity: loading ? 0.5 : 1,
              cursor: loading ? 'not-allowed' : 'text',
              transition: 'all 0.2s ease-in-out'
            }}
          />
          <button
            type="submit"
            disabled={loading}
            style={{ padding: '12px', cursor: loading ? 'not-allowed' : 'pointer', backgroundColor: loading ? '#4a5568' : '#007bff', color: '#fff', border: 'none', borderRadius: '6px', fontWeight: 'bold', fontSize: '15px', transition: 'background-color 0.2s' }}
          >
            {loading ? 'Searching...' : 'Ask'}
          </button>

          {(chatHistory.length > 0 || errorDetails) && (
            <button
              type="button"
              onClick={handleClearChat}
              disabled={loading}
              style={{
                padding: '5px',
                cursor: loading ? 'not-allowed' : 'pointer',
                backgroundColor: loading ? '#4a5568' : '#007bff',
                color: '#fff',
                border: 'none',
                borderRadius: '6px',
                fontWeight: 'bold',
                fontSize: '15px',
                transition: 'background-color 0.2s',
                opacity: loading ? 0.6 : 1
              }}
            >
              Clear
            </button>
          )}
        </form>
      </div>
    </div>
  );
}

export default App;
