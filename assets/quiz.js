document.querySelectorAll("[data-quiz]").forEach((quiz) => {
  const feedback = quiz.querySelector(".feedback");
  quiz.querySelectorAll("button[data-answer]").forEach((button) => {
    button.addEventListener("click", () => {
      const correct = button.dataset.answer === quiz.dataset.correct;
      feedback.textContent = correct ? quiz.dataset.success : quiz.dataset.retry;
      feedback.style.color = correct ? "#166534" : "#b91c1c";
    });
  });
});
