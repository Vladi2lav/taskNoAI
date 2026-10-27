import { Route, Routes } from 'react-router-dom'
import Nav from './components/Nav'
import Analytics from './pages/Analytics/Analytics'
import Status from './pages/Status/Status'
import Trades from './pages/Trades/Trades'

export default function App() {
  return (
    <div className="layout">
      <Nav />
      <main className="content">
        <Routes>
          <Route path="/" element={<Trades />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/status" element={<Status />} />
          <Route path="*" element={<p>Страница не найдена</p>} />
        </Routes>
      </main>
    </div>
  )
}
