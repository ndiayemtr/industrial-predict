import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { NbLayoutModule, NbSidebarModule } from '@nebular/theme';
import { SidebarComponent } from '../sidebar/sidebar.component';
import { HeaderComponent } from '../header/header.component';

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [NbLayoutModule, NbSidebarModule, RouterOutlet, SidebarComponent, HeaderComponent],
  templateUrl: './shell.component.html',
  styleUrl: './shell.component.scss'
})
export class ShellComponent {}
