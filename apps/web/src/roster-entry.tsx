import { createRoot } from 'react-dom/client'
import Roster from './Roster'
import './styles/kit.css'
import './styles/students.css'

createRoot(document.getElementById('root')!).render(
  <Roster />,
)
