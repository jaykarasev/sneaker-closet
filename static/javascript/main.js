document.getElementById("search-icon").addEventListener("click", function () {
  const searchContainer = document.querySelector(".search-container");
  const searchInput = document.getElementById("search-input");

  searchContainer.classList.toggle("expanded");

  if (searchContainer.classList.contains("expanded")) {
    searchInput.focus();
  }
});
