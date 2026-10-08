# Lab 2 Part C — chunking experiment

Run the 🧪 Mini eval for each setting, then copy the numbers from **Your experiments**.

| chunk size | overlap | top-K | doc hit | answer hit |
|---|---|---|---|---|
| 800 | 150 | 4 | 6/10 | 5/10 |
| 300 | 100 | 4 | 8/10 | 7/10 |
| 150 | 50 | 4 | 9/10 | 8/10 |
| 800 | 150 | 2 | 7/10 | 6/10 |

**What I learned (1–2 sentences):** Smaller chunks improved retrieval for specific policy questions because the matching text stayed more focused. Lower top-K values kept the answer list tighter, but a slightly larger top-K helped when the best answer was spread across multiple neighboring passages.

## ⭐ Stretch: 3 questions this app answers badly
1. Which cafeteria serves vegan food on Fridays?
2. What is Orbit Corp's parental leave policy?
3. Can I get permanent admin rights on my laptop?
