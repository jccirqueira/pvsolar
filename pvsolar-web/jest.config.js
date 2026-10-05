module.exports = {
  testEnvironment: 'jsdom',
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/$1',
  },
  transform: {
    '^.+\\.tsx?$': ['ts-jest', {
      tsconfig: {
        jsx: 'react-jsx',
        module: 'esnext',
        moduleResolution: 'bundler',
        esModuleInterop: true,
        strict: true,
        target: 'es5',
        paths: { '@/*': ['./src/*'] },
      },
    }],
  },
  testPathIgnorePatterns: ['<rootDir>/.next/', '<rootDir>/node_modules/'],
  // Piso de cobertura (gate da CI): atual ~97/67/97/97 - nunca regredir.
  coverageThreshold: {
    global: {
      statements: 90,
      branches: 60,
      functions: 90,
      lines: 90,
    },
  },
};
