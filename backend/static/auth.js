const mode = document.body.dataset.mode;
const form = document.querySelector('form');
const message = document.querySelector('.message');
const button = document.querySelector('button[type="submit"]');

function showMessage(text, success = false) {
    message.textContent = text;
    message.classList.toggle('success', success);
}

async function setupRedirect() {
    const response = await fetch('/api/setup/status');
    if (!response.ok) return;
    const status = await response.json();
    if (mode === 'login' && status.setup_required) location.replace('/setup');
    if (mode === 'setup' && !status.setup_required) location.replace('/login');
}

form.addEventListener('submit', async (event) => {
    event.preventDefault();
    button.disabled = true;
    showMessage('');
    const values = Object.fromEntries(new FormData(form).entries());
    const endpoint = mode === 'setup' ? '/api/setup/admin' : '/api/auth/login';
    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(values)
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || 'Request failed');
        if (mode === 'setup') {
            showMessage('Administrator created. Continue to sign in.', true);
            setTimeout(() => location.replace('/login'), 650);
        } else {
            location.replace('/');
        }
    } catch (error) {
        showMessage(error.message || 'Request failed');
        button.disabled = false;
    }
});

setupRedirect().catch(() => {});
