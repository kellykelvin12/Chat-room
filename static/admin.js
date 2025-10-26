function revealField(button, value) {
    const container = button.closest('.masked-field');
    const valueElement = container.querySelector('code, span:not(.btn-reveal)');
    // If value not passed, read from data-value attribute
    if (typeof value === 'undefined') {
        value = button.getAttribute('data-value') || '';
    }

    if (button.textContent === 'Show') {
        valueElement.textContent = value;
        button.textContent = 'Hide';
        button.style.background = '#f44336'; // Red for hide button
    } else {
        try{
            const prefixLen = value.startsWith('pbkdf2') ? 12 : 3;
            valueElement.textContent = value.substring(0, prefixLen) + '***';
        }catch(e){
            valueElement.textContent = '***';
        }
        button.textContent = 'Show';
        button.style.background = '#4CAF50'; // Green for show button
    }
}