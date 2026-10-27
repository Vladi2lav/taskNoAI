import { NavLink } from 'react-router-dom'

export default function Nav() {
  return (
    <nav className="sidebar">
      <div className="logo">Итоги торгов</div>
      <NavLink to="/" end>Сделки</NavLink>
      <NavLink to="/analytics">Аналитика</NavLink>
      <NavLink to="/status">Состояние данных</NavLink>
    </nav>
  )
}
