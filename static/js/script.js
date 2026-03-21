document.addEventListener("DOMContentLoaded", function () {
	const menuButton = document.getElementById("menuToggle");
	const sidebar = document.querySelector(".sidebar");

	if (menuButton && sidebar) {
		menuButton.addEventListener("click", function () {
			sidebar.classList.toggle("open");
		});
	}

	const currentPath = window.location.pathname;
	document.querySelectorAll(".sidebar-link").forEach(function (link) {
		if (link.getAttribute("href") === currentPath) {
			link.classList.add("active");
		}
	});

	document.querySelectorAll(".login-card, .panel, .auth-card").forEach(function (element, index) {
		element.style.opacity = "0";
		element.style.transform = "translateY(8px)";
		setTimeout(function () {
			element.style.transition = "all 0.4s ease";
			element.style.opacity = "1";
			element.style.transform = "translateY(0)";
		}, index * 90 + 120);
	});
});
