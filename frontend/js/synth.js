async function playSynthesizedMorse(text, wpm, freqHz, audioElement) {
  const blob = await Api.synthesize(text, wpm, freqHz);
  const url = URL.createObjectURL(blob);
  audioElement.src = url;
  await audioElement.play();
  return url;
}
