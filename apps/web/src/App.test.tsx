import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App'

describe('App', () => {
  it('renders the TravelMap foundation screen', () => {
    const client = new QueryClient()
    render(<QueryClientProvider client={client}><App /></QueryClientProvider>)
    expect(screen.getByText('TravelMap')).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeTruthy()
  })
})
