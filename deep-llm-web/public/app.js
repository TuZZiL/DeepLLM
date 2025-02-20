const messagesContainer = document.getElementById('messages');
const messageTemplate = document.getElementById('messageTemplate');
const messageInput = document.getElementById('messageInput');
const sendButton = document.getElementById('sendButton');
const themeToggle = document.querySelector('.theme-toggle');
const typingIndicator = document.getElementById('typingIndicator');
const errorToast = document.getElementById('errorToast');

let isStreaming = false;

const defaultSystemPrompt = "You are a helpful NSFW assistant.";

// Theme handling
function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
}

function loadTheme() {
    const savedTheme = localStorage.getItem('theme') ||
        (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
    setTheme(savedTheme);
}

// Message handling.  This function is only for user messages now.
function addMessage(content, isUser = false) {
    // Clone the template
    const messageDiv = messageTemplate.content.cloneNode(true).querySelector('.message');

    // Add user/ai class
    messageDiv.classList.add(isUser ? 'user' : 'ai');

    if (isUser) {
        messageDiv.querySelector('.reasoning-header').style.display = 'none';
    }

    // Get content elements
    const messageContent = messageDiv.querySelector('.message-content');
    const reasoningContainer = messageDiv.querySelector('.reasoning-container');
    const reasoningContent = reasoningContainer.querySelector('.reasoning-content');
    const reasoningToggle = messageDiv.querySelector('.reasoning-toggle');

    // Add event listener to toggle button
    reasoningToggle.addEventListener('click', () => {
        reasoningContainer.classList.toggle('collapsed');
    });

    try {
        messageContent.innerHTML = marked.parse(content);
    } catch (e) {
        messageContent.textContent = content;
        console.error('Markdown parsing error:', e);
    }

    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

async function sendMessage() {
    if (!messageInput.value.trim() || isStreaming) return;

    const userMessage = messageInput.value;
    messageInput.value = '';
    addMessage(userMessage, true); // Add the user message immediately

    try {
        isStreaming = true;
        typingIndicator.classList.add('active');

        const systemPrompt = document.getElementById('systemPrompt').value || defaultSystemPrompt;
        const messages = [{ role: 'user', content: userMessage }];
        messages.unshift({ role: 'system', content: systemPrompt });

        const params = getParameterValues();
        const urlParams = new URLSearchParams({
            messages: JSON.stringify(messages),
            temperature: params.temperature,
            top_p: params.top_p,
            frequency_penalty: params.frequency_penalty,
            presence_penalty: params.presence_penalty,
            max_tokens: params.max_tokens
        });

        const eventSource = new EventSource(`/api/chat?${urlParams.toString()}`);

        let currentReasoning = ''; // Accumulate reasoning parts
        let currentMessage = '';  // Accumulate message parts
        let messageDiv = null;    // The current message <div> element

        eventSource.onmessage = (event) => {
            const { content } = JSON.parse(event.data);

            // Find the last occurrence of </think> to handle reasoning
            const reasoningEnd = content.lastIndexOf('</think>');

            let reasoningPart = '';
            let messagePart = content;

            if (reasoningEnd !== -1) {
                // Split the content into reasoning and message parts
                reasoningPart = content.substring(0, reasoningEnd);
                messagePart = content.substring(reasoningEnd + 8); // Length of "</think>" is 8

                // Extract reasoning text (remove leading \n)
                const reasoningStart = reasoningPart.indexOf('\n');
                if (reasoningStart !== -1) {
                    reasoningPart = reasoningPart.substring(reasoningStart + 1);
                }
            }

            currentReasoning += reasoningPart;
            currentMessage += messagePart;

            if (!messageDiv) {
                // Clone the template for the *first* AI message part
                messageDiv = messageTemplate.content.cloneNode(true).querySelector('.message');
                messageDiv.classList.add('ai');
                const messageContentEl = messageDiv.querySelector('.message-content');
                const reasoningContainerEl = messageDiv.querySelector('.reasoning-container');
                const reasoningContentEl = reasoningContainerEl.querySelector('.reasoning-content');
                const reasoningToggle = messageDiv.querySelector('.reasoning-toggle');

                // Add event listener to toggle button
                reasoningToggle.addEventListener('click', () => {
                    reasoningContainerEl.classList.toggle('collapsed');
                });
                messagesContainer.appendChild(messageDiv);
            }

            // Update the content of existing elements
            const messageContentEl = messageDiv.querySelector('.message-content');
            const reasoningContainerEl = messageDiv.querySelector('.reasoning-container');
            const reasoningContentEl = reasoningContainerEl.querySelector('.reasoning-content');
            messageContentEl.innerHTML = marked.parse(currentMessage);
            reasoningContentEl.innerHTML = marked.parse(currentReasoning);
            messagesContainer.scrollTop = messagesContainer.scrollHeight; // Ensure scroll to bottom

            if (content.includes('</think>')) {
                // Reset for the next message
                currentReasoning = '';
                currentMessage = '';
                messageDiv = null;
            }
        };

        eventSource.onerror = () => {
            eventSource.close();
            isStreaming = false;
            typingIndicator.classList.remove('active');
        };

    } catch (error) {
        showError('Failed to connect to AI service' + error);
        isStreaming = false;
        typingIndicator.classList.remove('active');
    }
}

// Function to get parameter values
function getParameterValues() {
    return {
        temperature: parseFloat(temperatureValueInput.value),
        top_p: parseFloat(topPValueInput.value),
        frequency_penalty: parseFloat(frequencyPenaltyValueInput.value),
        presence_penalty: parseFloat(presencePenaltyValueInput.value),
        max_tokens: parseInt(maxTokensValueInput.value)
    };
}


// Error handling
function showError(message) {
    errorToast.textContent = message;
    errorToast.style.display = 'block';
    setTimeout(() => {
        errorToast.style.display = 'none';
    }, 5000);
}

// Event listeners
sendButton.addEventListener('click', sendMessage);
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

themeToggle.addEventListener('click', () => {
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
    setTheme(currentTheme === 'dark' ? 'light' : 'dark');
});

// Auto-resize textarea
messageInput.addEventListener('input', () => {
    messageInput.style.height = 'auto';
    messageInput.style.height = `${messageInput.scrollHeight}px`;
});

const paramsSidebar = document.getElementById('paramsSidebar');
const toggleParamsButton = document.getElementById('toggleParams');

// Parameter sidebar toggle
toggleParamsButton.addEventListener('click', () => {
    paramsSidebar.classList.toggle('open');
});


const temperatureSlider = document.getElementById('temperature');
const temperatureValueInput = document.getElementById('temperatureValue');
const topPSlider = document.getElementById('top_p');
const topPValueInput = document.getElementById('topPValue');
const frequencyPenaltySlider = document.getElementById('frequency_penalty');
const frequencyPenaltyValueInput = document.getElementById('frequencyPenaltyValue');
const presencePenaltySlider = document.getElementById('presence_penalty');
const presencePenaltyValueInput = document.getElementById('presencePenaltyValue');
const maxTokensSlider = document.getElementById('max_tokens');
const maxTokensValueInput = document.getElementById('maxTokensValue');

// Function to update number input when slider changes
function updateNumberInput(slider, numberInput) {
    numberInput.value = slider.value;
}

// Function to update slider when number input changes
function updateSlider(numberInput, slider) {
    slider.value = numberInput.value;
}

// Event listeners for sliders
temperatureSlider.addEventListener('input', () => updateNumberInput(temperatureSlider, temperatureValueInput));
topPSlider.addEventListener('input', () => updateNumberInput(topPSlider, topPValueInput));
frequencyPenaltySlider.addEventListener('input', () => updateNumberInput(frequencyPenaltySlider, frequencyPenaltyValueInput));
presencePenaltySlider.addEventListener('input', () => updateNumberInput(presencePenaltySlider, presencePenaltyValueInput));
maxTokensSlider.addEventListener('input', () => updateNumberInput(maxTokensSlider, maxTokensValueInput));

// Event listeners for number inputs
temperatureValueInput.addEventListener('change', () => updateSlider(temperatureValueInput, temperatureSlider));
topPValueInput.addEventListener('change', () => updateSlider(topPValueInput, topPSlider));
frequencyPenaltyValueInput.addEventListener('change', () => updateSlider(frequencyPenaltyValueInput, frequencyPenaltySlider));
presencePenaltyValueInput.addEventListener('change', () => updateSlider(presencePenaltyValueInput, presencePenaltySlider));
maxTokensValueInput.addEventListener('change', () => updateSlider(maxTokensValueInput, maxTokensSlider));


// Parameter sidebar toggle
toggleParamsButton.addEventListener('click', () => {
  if (paramsSidebar.style.width === '300px') {
    paramsSidebar.style.width = '0';
    paramsSidebar.style.visibility = 'hidden';
  } else {
    paramsSidebar.style.width = '300px';
    paramsSidebar.style.visibility = 'visible';
  }
});

// Initialize
loadTheme();
