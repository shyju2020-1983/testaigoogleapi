import React, { useState, useEffect, useRef } from 'react';

function App() {
  const [query, setQuery] = useState('');
  const [chatHistory, setChatHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [errorDetails, setErrorDetails] = useState(null);

  // AUTOFILL STATES FOR HEADINGS
  const [allHeadings, setAllHeadings] = useState([]);
  const [filteredHeadings, setFilteredHeadings] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const suggestionsListRef = useRef(null);

  // ANIMATED LIGHT BLUE PLACEHOLDER & ADVERTISEMENT ROTATION STATES (EVERY 2 SECONDS)
  const [placeholderText, setPlaceholderText] = useState('Ask question about kadirur');
  const [followUpPlaceholder, setFollowUpPlaceholder] = useState('Ask follow-up question');
  const [adText, setAdText] = useState('For advertisement contact 8078521983 or type ADS ');

  const ec2PublicIp = "13.233.119.28";
  const baseUrl = `http://${ec2PublicIp}:8000`;
  // Below code for local running
  // const baseUrl = 'http://localhost:8000';

  // FETCH ALL HEADINGS FROM BACKEND ON LOAD
  useEffect(() => {
    fetch(`${baseUrl}/api/headings`)
      .then((res) => res.json())
      .then((data) => {
        if (data && Array.isArray(data.headings)) {
          setAllHeadings(data.headings);
        }
      })
      .catch((err) => console.error('Failed to fetch headings for autofill:', err));
  }, [baseUrl]);

  useEffect(() => {
    let isEnglish = true;

    const interval = setInterval(() => {
      isEnglish = !isEnglish;

      if (isEnglish) {
        setPlaceholderText('Ask question about Kadirur');
        setFollowUpPlaceholder('Ask follow-up question');
        setAdText('For advertisement contact 8078521983 or type ADS');
      } else {
        setPlaceholderText('കതിരൂരിനെക്കുറിച്ച് ചോദ്യം ചോദിക്കാം');
        setFollowUpPlaceholder('തുടർച്ചോദ്യങ്ങൾ ചോദിക്കാം');
        setAdText('പരസ്യങ്ങൾക്കായി ബന്ധപ്പെടുക 8078521983 അല്ലെ ടൈപ്പ് ADS');
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

  // FILTER HEADINGS AS USER TYPES (CASE-INSENSITIVE STARTS-WITH)
  const handleInputChange = (e) => {
    const value = e.target.value;
    setQuery(value);
    setActiveIndex(-1);

    const searchVal = value.trim().toLowerCase();
    if (!searchVal) {
      setFilteredHeadings([]);
      setShowSuggestions(false);
      return;
    }

    const matches = allHeadings.filter((heading) =>
      String(heading).trim().toLowerCase().startsWith(searchVal)
    );
    setFilteredHeadings(matches);
    setShowSuggestions(matches.length > 0);
  };

  // AUTOFILL INPUT WHEN USER CLICKS OR SELECTS A HEADING SUGGESTION
  const handleSelectHeading = (heading) => {
    setQuery(heading);
    setFilteredHeadings([]);
    setShowSuggestions(false);
    setActiveIndex(-1);
  };

  // KEYBOARD NAVIGATION FOR AUTOFILL DROPDOWN
  const handleKeyDown = (e) => {
    if (!showSuggestions || filteredHeadings.length === 0) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex((prev) => {
        const nextIndex = prev < filteredHeadings.length - 1 ? prev + 1 : 0;
        suggestionsListRef.current?.children[nextIndex]?.scrollIntoView({ block: 'nearest' });
        return nextIndex;
      });
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((prev) => {
        const nextIndex = prev > 0 ? prev - 1 : filteredHeadings.length - 1;
        suggestionsListRef.current?.children[nextIndex]?.scrollIntoView({ block: 'nearest' });
        return nextIndex;
      });
    } else if (e.key === 'Enter' && activeIndex >= 0) {
      e.preventDefault();
      handleSelectHeading(filteredHeadings[activeIndex]);
    } else if (e.key === 'Escape') {
      setShowSuggestions(false);
      setActiveIndex(-1);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    const currentQuery = query;
    setQuery('');
    setShowSuggestions(false);
    setActiveIndex(-1);
    setLoading(true);
    setErrorDetails(null);

    const targetUrl = `${baseUrl}/api/query`;

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
    setFilteredHeadings([]);
    setShowSuggestions(false);
    setActiveIndex(-1);
  };

  return (
    <div style={{ position: 'relative', backgroundColor: '#121212', minHeight: '100vh', width: '100%', padding: '40px 0 240px 0', boxSizing: 'border-box' }}>
           <style>{`
        .custom-chat-input::placeholder {
          color: #7caee3 !important;
          opacity: 1;
        }

        /* Stylish thin scrollbar for Laptop & Mobile */
        .autofill-dropdown {
          overflow-y: auto;
          overscroll-behavior: contain;
          -webkit-overflow-scrolling: touch;
          scrollbar-width: thin;
          scrollbar-color: #94979a #181818;
        }

        .autofill-dropdown::-webkit-scrollbar {
          width: 6px;
          height: 6px;
        }

        .autofill-dropdown::-webkit-scrollbar-track {
          background: #181818;
          border-radius: 0 6px 6px 0;
          margin: 4px 0;
        }

        .autofill-dropdown::-webkit-scrollbar-thumb {
          background: linear-gradient(180deg, #3395ff 0%, #0062cc 100%);
          border-radius: 999px;
          border: 1px solid #181818;
        }

        .autofill-dropdown::-webkit-scrollbar-thumb:hover {
          background: #52a8ff;
        }

        /* Mobile View Optimization */
        @media (max-width: 640px) {
          .autofill-dropdown {
            max-height: 180px !important;
          }

          .autofill-dropdown::-webkit-scrollbar {
            width: 4px;
          }

          .autofill-dropdown::-webkit-scrollbar-thumb {
            background: #007bff;
            border: none;
          }
        }
      `}</style>


      <div style={{ maxWidth: '600px', margin: '0 auto', padding: '20px', fontFamily: 'sans-serif', color: '#ffffff' }}>
        <h2 style={{ margin: '0 0 8px 0', textAlign: 'center', color: '#007bff', padding: '0 45px', fontSize: '20px' }}>
          <b>Kadirur village AI Assistant</b>
        </h2>

        {/* TOP ROTATING ADVERTISEMENT BANNER */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'center',
            paddingRight: '10px',
            marginBottom: '18px',
          }}
        >
          <div
            style={{
              backgroundColor: 'rgba(0, 123, 255, 0.12)',
              border: '1px solid rgba(0, 123, 255, 0.4)',
              borderRadius: '8px',
              padding: '6px 12px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              width: '100%',
              maxWidth: '380px',
              minHeight: '42px',
              boxSizing: 'border-box',
            }}
          >
            <span
              style={{
                backgroundColor: '#007bff',
                color: '#ffffff',
                fontSize: '10px',
                fontWeight: 'bold',
                padding: '2px 6px',
                borderRadius: '4px',
                letterSpacing: '0.5px',
              }}
            >
              AD
            </span>
            <span style={{ fontSize: '12.5px', fontWeight: '600', color: '#90caf9' }}>
              {adText}
            </span>
          </div>
        </div>

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
                  <strong style={{ color: '#007bff', fontSize: '12px' }}>English Response:</strong>
                  <p style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', marginTop: '5px', marginBottom: '0', color: '#e0e0e0', fontWeight: '500', lineHeight: '1.5', fontSize: '15px' }}>
                    {linkify(englishReply || chat.answer)}
                  </p>

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

        {/* PERSISTENT INPUT ROW WITH DOWNWARD AUTOFILL DROPDOWN */}
        <form
          onSubmit={handleSubmit}
          style={{ display: 'flex', gap: '10px', marginTop: '20px', position: 'sticky', bottom: '20px', backgroundColor: '#121212', padding: '10px 0', zIndex: 50 }}
        >
          {/* Input + Floating Suggestions Wrapper */}
          <div style={{ position: 'relative', flexGrow: 1, display: 'flex' }}>
            {showSuggestions && filteredHeadings.length > 0 && (
                           <ul
                ref={suggestionsListRef}
                className="autofill-dropdown"
                style={{
                  position: 'absolute',
                  top: '100%',
                  left: 0,
                  right: 0,
                  marginTop: '6px',
                  padding: 0,
                  listStyle: 'none',
                  backgroundColor: '#1e1e1e',
                  border: '1px solid #444',
                  borderRadius: '6px',
                  maxHeight: '220px',
                  overflowY: 'auto',
                  boxShadow: '0 4px 12px rgba(0, 0, 0, 0.5)',
                  zIndex: 100
                }}
              

              >
                {filteredHeadings.map((heading, idx) => (
                  <li
                    key={idx}
                    onMouseDown={() => handleSelectHeading(heading)}
                    onMouseEnter={() => setActiveIndex(idx)}
                    style={{
                      padding: '10px 14px',
                      cursor: 'pointer',
                      color: '#fff',
                      fontSize: '14px',
                      backgroundColor: idx === activeIndex ? '#007bff' : 'transparent',
                      borderBottom: idx !== filteredHeadings.length - 1 ? '1px solid #2d2d2d' : 'none',
                      transition: 'background-color 0.15s'
                    }}
                  >
                    {heading}
                  </li>
                ))}
              </ul>
            )}

            <input
              type="text"
              autoComplete="off"
              className="custom-chat-input"
              value={query}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              onFocus={() => {
                if (query.trim() && filteredHeadings.length > 0) {
                  setShowSuggestions(true);
                }
              }}
              onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
              placeholder={(chatHistory.length > 0 || loading) ? followUpPlaceholder : placeholderText}
              disabled={loading}
              style={{
                width: '100%',
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
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{
              padding: '12px',
              cursor: loading ? 'not-allowed' : 'pointer',
              backgroundColor: loading ? '#4a5568' : '#007bff',
              color: '#fff',
              border: 'none',
              borderRadius: '6px',
              fontWeight: 'bold',
              fontSize: '15px',
              transition: 'background-color 0.2s'
            }}
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
