// Featured videos from localStorage
let favorites = JSON.parse(localStorage.getItem('favorites')) || [];

// Update Favorites Buttons
function updateFavoriteButtons() {
    const favoriteButtons = document.querySelectorAll('.favorite-btn[data-video]');
    favoriteButtons.forEach(button => {
        const videoUrl = button.getAttribute('data-video');
        if (favorites.includes(videoUrl)) {
            // Add to Favorites
            button.classList.add('active');
            button.innerHTML = '<i class="far fa-star"></i>'; // Remove from Favorites
        } else {
            // Remove from Favorites
            button.classList.remove('active');
            button.innerHTML = '<i class="fas fa-star"></i>'; // Add to Favorites
        }
    });
}

// Favorites button click handler
document.body.addEventListener('click', function (e) {
    const favoriteBtn = e.target.closest('.favorite-btn[data-video]');
    if (favoriteBtn) {
        const videoUrl = favoriteBtn.getAttribute('data-video');
        if (!videoUrl) return;

        if (favorites.includes(videoUrl)) {
            // Remove from Favorites
            favorites = favorites.filter(fav => fav !== videoUrl);
            favoriteBtn.classList.remove('active');
            favoriteBtn.innerHTML = '<i class="fas fa-star"></i>'; // Add to Favorites
        } else {
            // Add to Favorites
            favorites.push(videoUrl);
            favoriteBtn.classList.add('active');
            favoriteBtn.innerHTML = '<i class="far fa-star"></i>'; // Remove from Favorites
        }

        localStorage.setItem('favorites', JSON.stringify(favorites));
        updateFavoritesList();
    }
});

// Update your favorites list in offcanvas
function updateFavoritesList() {
    const favoritesList = document.getElementById('favoritesList');
    favoritesList.innerHTML = '';
    if (favorites.length === 0) {
        const emptyMessage = document.createElement('p');
        emptyMessage.textContent = 'List is empty';
        favoritesList.appendChild(emptyMessage);
    } else {
        favorites.forEach(videoUrl => {
            // const [id, video] = videoUrl.split('/');
            const [id] = videoUrl.split('/');
            const listItem = document.createElement('li');
            listItem.className = 'list-group-item';
            const link = document.createElement('a');
            // link.href = `/video/${id}/${video}`;
            // link.textContent = video.replace(/\.(mp4|avi|mkv)$/i, '');
            link.href = `/video/${id}`;
            link.textContent = id;
            link.className = 'text-dark';
            listItem.appendChild(link);
            favoritesList.appendChild(listItem);
        });
    }
}

// Initialization
updateFavoriteButtons();
updateFavoritesList();
