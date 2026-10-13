import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { NbLayoutModule, NbSidebarModule } from '@nebular/theme';

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [NbLayoutModule, NbSidebarModule, RouterOutlet],
  templateUrl: './shell.component.html',
  styleUrl: './shell.component.scss'
})
export class ShellComponent {}
