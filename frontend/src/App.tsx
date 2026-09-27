import { RouterProvider } from 'react-router-dom';
import router from './router';
import { useOnlineStatus } from './hooks/useOnlineStatus';
import OfflineBanner from './components/ui/OfflineBanner';

function App() {
  const { isOnline } = useOnlineStatus();

  return (
    <>
      {!isOnline && <OfflineBanner />}
      <RouterProvider router={router} />
    </>
  );
}

export default App;
