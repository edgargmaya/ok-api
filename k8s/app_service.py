import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import os
import sys

class AppServerSvc(win32serviceutil.ServiceFramework):
    _svc_name_ = 'NombreDeTuServicio'
    _svc_display_name_ = 'Nombre Descriptivo de Tu Servicio'
    _svc_description_ = 'Descripción breve de lo que hace tu servicio'

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        self.main()

    def main(self):
        # Ejecuta tu aplicación principal
        # Asegúrate de proporcionar la ruta completa si es necesario
        os.system(f'python "{os.path.abspath("app.py")}"')

if __name__ == '__main__':
    if len(sys.argv) == 1:
        # Ejecutar como servicio
        win32serviceutil.HandleCommandLine(AppServerSvc)
    else:
        # Manejar instalación con opciones personalizadas
        win32serviceutil.HandleCommandLine(
            AppServerSvc,
            serviceClassString='tu_script_servicio.AppServerSvc',
            argv=sys.argv
        )
