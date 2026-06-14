// SmartGram Pro – main.js

// Auto-dismiss flash messages after 4 seconds
document.addEventListener('DOMContentLoaded', () => {
  setTimeout(() => {
    document.querySelectorAll('.flash-toast').forEach(el => {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(el);
      bsAlert.close();
    });
  }, 4000);

  // Animate stat numbers on home page
  document.querySelectorAll('.stat-number').forEach(el => {
    const target = parseInt(el.textContent) || 0;
    let current = 0;
    const step = Math.ceil(target / 40);
    const timer = setInterval(() => {
      current = Math.min(current + step, target);
      el.textContent = current;
      if (current >= target) clearInterval(timer);
    }, 30);
  });

  // Navbar scroll effect
  const nav = document.getElementById('mainNav');
  if (nav) {
    window.addEventListener('scroll', () => {
      nav.style.background = window.scrollY > 50
        ? 'rgba(15,23,42,0.98)'
        : 'rgba(15,23,42,0.95)';
    });
  }
});

// Toggle password visibility
function togglePassword(fieldId) {
  const field = document.getElementById(fieldId);
  const eye   = document.getElementById(fieldId + '-eye');
  if (!field) return;
  if (field.type === 'password') {
    field.type = 'text';
    eye && (eye.className = 'fas fa-eye-slash');
  } else {
    field.type = 'password';
    eye && (eye.className = 'fas fa-eye');
  }
}
