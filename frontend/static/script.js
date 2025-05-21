const log = document.getElementById("log");
let history = [];

document.addEventListener('DOMContentLoaded', () => {
    const chatBox = document.getElementById('chat-box');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');

    // Generate a new UUID for the sessionThreadId on every page load
    let sessionThreadId;
    if (window.crypto && window.crypto.randomUUID) {
        sessionThreadId = window.crypto.randomUUID();
    } else {
        // Fallback for older browsers
        console.warn('crypto.randomUUID not available, using fallback ID generator.');
        sessionThreadId = 'user-' + Date.now() + '-' + Math.random().toString(36).substring(2, 15);
    }
    console.log("New Session Thread ID (UUID):", sessionThreadId);

    sendButton.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });

    // Add event listener for page unload to notify the backend
    window.addEventListener('unload', function() {
        if (sessionThreadId) {
            const payload = JSON.stringify({ thread_id: sessionThreadId });
            const blob = new Blob([payload], { type: 'application/json; charset=UTF-8' });
            const goodbyeUrl = `${BACKEND_BASE_URL}/api/goodbye`; 
            try {
                if (navigator.sendBeacon(goodbyeUrl, blob)) { 
                    console.log("Successfully queued beacon to clear memory for thread ID:", sessionThreadId, "to URL:", goodbyeUrl);
                } else {
                    console.error("Failed to queue beacon for thread ID:", sessionThreadId, "to URL:", goodbyeUrl);
                }
            } catch (e) {
                console.error("Error sending beacon to", goodbyeUrl, ":", e);
            }
        }
    });

    const BACKEND_BASE_URL = 'http://localhost:8000'; // Modified in production build

    function formatMessageText(text) {
        let formattedText = text;

        // 1. Convert **bold text** to <strong>bold text</strong>
        formattedText = formattedText.replace(/\*\*([^\*\*]+)\*\*/g, '<strong>$1</strong>');
        // 2. Convert bullet points (e.g., * item or - item) to HTML lists    
        // Convert individual list items: * item -> <li>item</li>
        const listItems = [];
        let inList = false;
        const lines = formattedText.split('\n');
        let processedLines = [];

        for (const line of lines) {
            if (line.match(/^([\*\-])\s+(.+)/)) {
                if (!inList) {
                    processedLines.push('<ul>');
                    inList = true;
                }
                processedLines.push(line.replace(/^([\*\-])\s+(.+)/, '<li>$2</li>'));
            } else {
                if (inList) {
                    processedLines.push('</ul>');
                    inList = false;
                }
                processedLines.push(line);
            }
        }
        if (inList) { 
            processedLines.push('</ul>');
        }
        formattedText = processedLines.join('\n');

        // Replace newline characters with <br> tags for lines not part of lists for HTML rendering
        // This should be done carefully to not break list structure.
        // The previous white-space: pre-wrap; handles most cases, but if we use innerHTML extensively,
        // explicit <br> might be needed for non-list newlines.
        // For now, relying on pre-wrap and the list conversion.
        
        return formattedText;
    }

    function displaySources(messageRowElement, sources) {
        // console.log("[displaySources] Called with sources:", sources);
        // console.log("[displaySources] messageRowElement:", messageRowElement);

        if (!sources || sources.length === 0) {
            // console.log("[displaySources] No sources or empty array, returning.");
            return;
        }

        if (messageRowElement.querySelector('.message-sources-container')) {
            // console.log("[displaySources] Sources container already exists for this row, aborting to prevent duplication.");
            return;
        }

        const sourcesContainer = document.createElement('div');
        sourcesContainer.classList.add('message-sources-container');

        const titleElement = document.createElement('h4');
        titleElement.textContent = 'Fuentes:';
        sourcesContainer.appendChild(titleElement);

        const listElement = document.createElement('ul');
        sources.forEach(source => {
            const listItem = document.createElement('li');
            const link = document.createElement('a');
            link.href = source.url;
            link.textContent = source.title || 'Enlace'; // Fallback text
            link.target = '_blank'; // Open in new tab
            link.rel = 'noopener noreferrer';
            listItem.appendChild(link);
            listElement.appendChild(listItem);
        });
        sourcesContainer.appendChild(listElement);
        
        // console.log("[displaySources] Appending sourcesContainer:", sourcesContainer, "to messageRowElement:", messageRowElement);
        messageRowElement.appendChild(sourcesContainer);
        chatBox.scrollTop = chatBox.scrollHeight;
        // console.log("[displaySources] Finished appending sources.");
    }

    function appendMessage(text, messageTypeClass) {
        const messageRow = document.createElement('div');
        messageRow.classList.add('message-row');

        const messageElement = document.createElement('div');
        messageElement.classList.add('message', messageTypeClass); 
        
        messageElement.innerHTML = formatMessageText(text);

        if (messageTypeClass === 'user-message') {
            messageRow.classList.add('user-message-row');
        } else if (messageTypeClass === 'bot-message') {
            messageRow.classList.add('bot-message-row');
        }

        messageRow.appendChild(messageElement);
        chatBox.appendChild(messageRow);
        chatBox.scrollTop = chatBox.scrollHeight; 
    }

    function showLoadingIndicator() {
        const chatBox = document.getElementById('chat-box');
        if (document.getElementById('loading-indicator')) return;

        const loadingRow = document.createElement('div');
        loadingRow.classList.add('message-row', 'loading-dots-row', 'bot-message-row'); // Add bot-message-row for alignment
        loadingRow.id = 'loading-indicator'; 

        const loadingElement = document.createElement('div');
        loadingElement.classList.add('loading-dots'); 
        loadingElement.id = 'pending-bot-message'; // ID for the actual message bubble part
        loadingElement.innerHTML = '<span></span><span></span><span></span>';

        loadingRow.appendChild(loadingElement);
        chatBox.appendChild(loadingRow);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    function removeLoadingIndicatorAndPrepareMessageElement() {
        const loadingRow = document.getElementById('loading-indicator');
        if (loadingRow) {
            const botMessageElement = document.getElementById('pending-bot-message');
            if (botMessageElement) {
                // Transform into a bot message element
                botMessageElement.classList.remove('loading-dots');
                botMessageElement.classList.add('message', 'bot-message');
                botMessageElement.innerHTML = ''; 
                loadingRow.removeAttribute('id'); 
                botMessageElement.removeAttribute('id'); 
                return botMessageElement;
            } else {
                loadingRow.remove();
                return null;
            }
        } 
        return null; 
    }

    function sendMessage() {
        const messageText = userInput.value.trim();
        if (messageText === '') return;

        appendMessage(messageText, 'user-message');
        userInput.value = '';

        showLoadingIndicator();

        let botMessageElement = null;
        let currentBotText = "";

        fetch(`${BACKEND_BASE_URL}/api/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message: messageText, thread_id: sessionThreadId })
        })
        .then(response => {
            if (!response.ok) {
                const tempElem = removeLoadingIndicatorAndPrepareMessageElement();
                if (tempElem) tempElem.parentElement.remove();
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let firstChunkReceived = false;
            let buffer = ""; 

            function push() {
                reader.read().then(({ done, value }) => {
                    if (done) {
                        if (!firstChunkReceived && !buffer.trim()) { 
                           const tempElem = removeLoadingIndicatorAndPrepareMessageElement();
                           if (tempElem) tempElem.parentElement.remove(); 
                        }
                        
                        const sseBoundaryRegex = /\r\n\r\n|\n\n|\r\r|(\r\n|\n|\r){2,}/;
                        let searchResult = buffer.search(sseBoundaryRegex);

                        while (searchResult !== -1) {
                            const boundaryMatch = buffer.match(sseBoundaryRegex);
                            const boundaryLength = boundaryMatch ? boundaryMatch[0].length : 2; // Default to 2 if match is null (should not happen)
                            const message = buffer.substring(0, searchResult);
                            buffer = buffer.substring(searchResult + boundaryLength);

                            if (message.trim().startsWith("data:")) {
                                const jsonData = message.substring(message.indexOf("data:") + 5).trim();
                                if (jsonData) {
                                    try {
                                        const parsedData = JSON.parse(jsonData);
                                        console.log("Received final SSE data (loop from done):", parsedData);
                                        if (parsedData.token && botMessageElement) {
                                            currentBotText += parsedData.token;
                                            botMessageElement.innerHTML = formatMessageText(currentBotText);
                                            chatBox.scrollTop = chatBox.scrollHeight;
                                        } else if (parsedData.sources_used && botMessageElement) {
                                            displaySources(botMessageElement.parentElement, parsedData.sources_used);
                                        } else if (parsedData.event === 'end') {
                                            console.log("Processed final 'end' event from buffer (loop from done).");
                                            if (!botMessageElement && !firstChunkReceived) {
                                                const tempElem = removeLoadingIndicatorAndPrepareMessageElement();
                                                if (tempElem) tempElem.parentElement.remove();
                                            }
                                        }
                                    } catch (e) {
                                        console.error("Error parsing final buffered message (loop from done):", jsonData, e);
                                    }
                                }
                            } else if (message.trim()) {
                                console.log("Received final non-data SSE line (loop from done):", message);
                            }
                            searchResult = buffer.search(sseBoundaryRegex);
                        }
                    }

                    buffer += decoder.decode(value, { stream: true });
                    const sseBoundaryRegex = /\r\n\r\n|\n\n|\r\r|(\r\n|\n|\r){2,}/; 
                    let searchResult = buffer.search(sseBoundaryRegex);

                    while (searchResult !== -1) {
                        const boundaryMatch = buffer.match(sseBoundaryRegex);
                        const boundaryLength = boundaryMatch ? boundaryMatch[0].length : 2; 
                        const message = buffer.substring(0, searchResult);
                        buffer = buffer.substring(searchResult + boundaryLength);

                        if (message.trim().startsWith("data:")) {
                            const jsonData = message.substring(message.indexOf("data:") + 5).trim();
                            if (jsonData) {
                                try {
                                    const parsedData = JSON.parse(jsonData);
                                    // console.log("Received SSE data:", parsedData); // General SSE data log
                                    
                                    if (!firstChunkReceived) {
                                        botMessageElement = removeLoadingIndicatorAndPrepareMessageElement();
                                        if (!botMessageElement) { 
                                            console.error("Failed to get botMessageElement after first chunk.");
                                        }
                                        firstChunkReceived = true;
                                    }
                                    
                                    if (parsedData.token) {
                                        if (botMessageElement) {
                                            currentBotText += parsedData.token;
                                            botMessageElement.innerHTML = formatMessageText(currentBotText);
                                            chatBox.scrollTop = chatBox.scrollHeight;
                                        } else {
                                            console.warn("botMessageElement is null, cannot append token:", parsedData.token);
                                        }
                                    } else if (parsedData.sources_used) {
                                        // console.log("[DEBUG] sources_used received. botMessageElement:", botMessageElement); 
                                        if (botMessageElement) {
                                            displaySources(botMessageElement.parentElement, parsedData.sources_used);
                                        } else {
                                            console.warn("botMessageElement is null, cannot display sources.");
                                        }
                                    } else if (parsedData.event === 'end') {
                                        // console.log("Received 'end' event."); 
                                    }

                                } catch (e) {
                                    console.error("Error parsing stream data:", jsonData, e);
                                    if (!firstChunkReceived) {
                                        const tempElem = removeLoadingIndicatorAndPrepareMessageElement();
                                        if (tempElem) tempElem.parentElement.remove();
                                    }
                                    // Decide if we want to display an error in the chat.
                                    // appendMessage("Error processing server response.", 'bot-message error-message');
                                }
                            } else if (message.trim()) { // Non-empty line that doesn't start with "data:"
                                console.log("Received non-data SSE line:", message);
                            }
                            searchResult = buffer.search(sseBoundaryRegex);
                        }
                    }
                    push(); // Continue reading
                }).catch(error => {
                    console.error('Error reading from stream:', error);
                    if (!firstChunkReceived) {
                        const tempElem = removeLoadingIndicatorAndPrepareMessageElement();
                        if (tempElem) tempElem.parentElement.remove();
                    }
                    appendMessage("Error connecting to the server.", 'bot-message error-message');
                });
            }

            push(); // Start the reading process
        })
        .catch(error => {
            const tempElem = removeLoadingIndicatorAndPrepareMessageElement();
            if (tempElem) tempElem.parentElement.remove();
            
            console.error('Fetch Error:', error);
            appendMessage('Error al iniciar la conexión con el servidor. Inténtelo más tarde.', 'bot-message');
            chatBox.scrollTop = chatBox.scrollHeight;
        });
    }
});

function append(text) {
  log.textContent += "\n" + text;
  log.scrollTop = log.scrollHeight;
}