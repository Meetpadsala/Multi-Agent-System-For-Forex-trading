// Main JavaScript file for Forex Trading System

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips if Bootstrap tooltips are used
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    const tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Auto-refresh functionality for dashboard
    if (document.getElementById('priceChart')) {
        // Auto-refresh every 30 seconds
        setInterval(function() {
            if (document.getElementById('refreshBtn')) {
                document.getElementById('refreshBtn').click();
            }
        }, 30000);
    }

    // Handle symbol selection change
    const symbolSelect = document.getElementById('symbolSelect');
    if (symbolSelect) {
        symbolSelect.addEventListener('change', function() {
            // Auto-refresh when symbol changes
            if (document.getElementById('refreshBtn')) {
                document.getElementById('refreshBtn').click();
            }
        });
    }

    // Add loading states to buttons
    const buttons = document.querySelectorAll('.btn');
    buttons.forEach(button => {
        button.addEventListener('click', function() {
            if (this.hasAttribute('data-loading-text')) {
                const originalText = this.textContent;
                this.textContent = this.getAttribute('data-loading-text');
                this.disabled = true;

                // Re-enable after 2 seconds (for demo purposes)
                setTimeout(() => {
                    this.textContent = originalText;
                    this.disabled = false;
                }, 2000);
            }
        });
    });

    // Format numbers in tables
    const numberCells = document.querySelectorAll('.number-cell');
    numberCells.forEach(cell => {
        const value = parseFloat(cell.textContent);
        if (!isNaN(value)) {
            cell.textContent = value.toFixed(5);
        }
    });

    // Handle form submissions with AJAX where appropriate
    const forms = document.querySelectorAll('form[data-ajax="true"]');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            const formData = new FormData(this);
            const action = this.action;

            fetch(action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Handle success
                    showAlert('Success', 'Operation completed successfully', 'success');
                } else {
                    // Handle error
                    showAlert('Error', data.error || 'An error occurred', 'danger');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showAlert('Error', 'Network error occurred', 'danger');
            });
        });
    });
});

// Utility function to show alerts
function showAlert(title, message, type) {
    const alertContainer = document.getElementById('alertContainer') || createAlertContainer();

    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show`;
    alert.innerHTML = `
        <strong>${title}:</strong> ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

    alertContainer.appendChild(alert);

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        if (alert.parentNode) {
            alert.remove();
        }
    }, 5000);
}

// Create alert container if it doesn't exist
function createAlertContainer() {
    const container = document.createElement('div');
    container.id = 'alertContainer';
    container.className = 'position-fixed top-0 end-0 p-3';
    container.style.zIndex = '1050';
    document.body.appendChild(container);
    return container;
}

// Utility function for currency formatting
function formatCurrency(value, currency = 'USD') {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: currency,
        minimumFractionDigits: 5,
        maximumFractionDigits: 5
    }).format(value);
}

// Utility function for percentage formatting
function formatPercentage(value) {
    return (value).toFixed(2) + '%';
}

// Debounce function for search inputs
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Export functions for global use
window.ForexUtils = {
    formatCurrency,
    formatPercentage,
    showAlert,
    debounce
};
