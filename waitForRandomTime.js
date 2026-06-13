function sleepRandom() {
  const minutes = Math.floor(Math.random() * 2);   // 0–30
  const seconds = Math.floor(Math.random() * 60);   // 0–59

  const totalMs = (minutes * 60 + seconds) * 1000;

  console.log(`Sleeping for ${minutes} minute(s) and ${seconds} second(s)...`);

  return new Promise(resolve => setTimeout(resolve, totalMs));
}

(async () => {
  await sleepRandom();
  console.log("Wake up!");
})();
