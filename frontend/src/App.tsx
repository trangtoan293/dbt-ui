import { useState } from 'react'
import './App.css'
import ProjectCatalogDialog from './components/main/ProjectCatalogDialog'
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
        <ProjectCatalogDialog onOpen={handleOpen} />
      ) : (
        <MainLayout projectPath={projectPath} dbtVersion="" onChangeProject={handleChangeProject} />
      )}
    </div>
  )
}

export default App
