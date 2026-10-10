document.querySelectorAll('.sound-review-card audio').forEach(audio => audio.addEventListener('play', () => {
  document.querySelectorAll('.sound-review-card audio').forEach(other => { if (other !== audio) other.pause(); });
}));
