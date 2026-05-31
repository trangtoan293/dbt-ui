import { useState } from 'react'
import './App.css'
import ProjectDialog from './components/main/ProjectDialog'
import MainLayout from './components/main/MainLayout'

function App() {
  const [projectPath, setProjectPath] = useState<string | null>(null)
  const [projectName, setProjectName] = useState<string>('')

  const handleOpen = (path: string, name: string) => {
    setProjectPath(path)
    setProjectName(name)
  }

  const handleChangeProject = () => {
    setProjectPath(null)
    setProjectName('')
  }

  return (
    <div className="app">
      {!projectPath ? (
        <ProjectDialog onOpen={handleOpen} />
      ) : (
        <MainLayout projectPath={projectPath} projectName={projectName} dbtVersion="" onChangeProject={handleChangeProject} />
      )}
    </div>
  )
}

export default App
