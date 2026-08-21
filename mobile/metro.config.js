const { getDefaultConfig } = require('expo/metro-config');
const path = require('path');

const config = getDefaultConfig(__dirname);

// Block watching backend, virtual environments, and build artifacts
config.resolver.blockList = [
  /.*\/backend\/.*/,
  /.*\/\.venv\/.*/,
  /.*\/\.git\/.*/,
  /.*\/__pycache__\/.*/,
];

module.exports = config;
