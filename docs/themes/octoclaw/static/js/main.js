// Sidebar toggle (mobile)
document.addEventListener('DOMContentLoaded', function () {
  // Close sidebar on content click (mobile)
  var content = document.querySelector('.content');
  if (content) {
    content.addEventListener('click', function () {
      var sidebar = document.querySelector('.sidebar');
      if (sidebar) sidebar.classList.remove('sidebar--open');
    });
  }

  // Active sidebar link highlighting
  var currentPath = window.location.pathname;
  document.querySelectorAll('.sidebar__link').forEach(function (link) {
    if (link.getAttribute('href') === currentPath) {
      link.classList.add('sidebar__link--active');
    }
  });

  // Copy button on code blocks
  document.querySelectorAll('.prose pre').forEach(function (pre) {
    var wrapper = document.createElement('div');
    wrapper.className = 'code-block';
    pre.parentNode.insertBefore(wrapper, pre);
    wrapper.appendChild(pre);

    var btn = document.createElement('button');
    btn.className = 'code-block__copy';
    btn.textContent = 'Copy';
    btn.addEventListener('click', function () {
      var code = pre.querySelector('code');
      var text = code ? code.textContent : pre.textContent;
      navigator.clipboard.writeText(text).then(function () {
        btn.textContent = 'Copied';
        setTimeout(function () { btn.textContent = 'Copy'; }, 1500);
      });
    });
    wrapper.appendChild(btn);
  });

  // Smooth scroll for anchor links
  document.querySelectorAll('a[href^="#"]').forEach(function (link) {
    link.addEventListener('click', function (e) {
      var target = document.querySelector(this.getAttribute('href'));
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        history.pushState(null, null, this.getAttribute('href'));
      }
    });
  });
});
