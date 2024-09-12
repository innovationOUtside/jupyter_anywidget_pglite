const audioContext = new window.AudioContext();

// Speak a message aloud using a browser SpeechSynthesisUtterance
// The SpeechSynthesisUtterance object should be available
// for garbage collection after the message is spoken.
export const say = (message: string | null) => {
  if (message) {
    let utterance = new SpeechSynthesisUtterance(message);
    window.speechSynthesis.speak(utterance);
  }
};

export function play_tone(
  frequency: number = 440,
  duration_ms: number = 1000, //milliseconds
  volume: number = 0.1,
  type: OscillatorType = "sine", //  "sine", "square", "sawtooth", "triangle",  "custom"
  message: string | null = null
) {
  // Create a new AudioContext

  // Create an OscillatorNode
  const oscillator = audioContext.createOscillator();

  // Create a gain node
  const gain = audioContext.createGain();

  // Set the colume
  gain.gain.value = volume;

  // Set the type of the oscillator
  oscillator.type = type;

  // Set the frequency of the oscillator
  oscillator.frequency.value = frequency;

  // Connect the gain function
  oscillator.connect(gain);

  // Connect the oscillator to the audio context's destination (the speakers)
  oscillator.connect(audioContext.destination);

  // Start the oscillator immediately
  oscillator.start();

  // Set the gain envelope
  gain.gain.exponentialRampToValueAtTime(
    0.00001,
    audioContext.currentTime + duration_ms
  );

  // Stop the oscillator after the specified duration
  setTimeout(() => {
    oscillator.stop();
    if (message)
      setTimeout(() => {
        say(message);
      }, 100);
  }, duration_ms);
}

export function play_success(msg: string | null = null) {
  play_tone(500, 5, 0.05, "sine", msg);
}
